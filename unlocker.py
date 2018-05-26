#!/bin/env python3

from subprocess import check_output, run, PIPE, CalledProcessError
from time import sleep

from conf import *

ENCRYPTED = "encrypted"
MIXED = "mixed"
UNENCRYPTED = "unencrypted"

def yubikey_present():
	usb_devices = check_output('lsusb').decode()

	return 'Yubikey' in usb_devices


def disks_encrypted():
	states = set()
	lsblk = check_output('lsblk').decode()
	for disk in DISKS:
		states.add(disk in lsblk)

	if len(states) == 1:  # Uniform state
		return UNENCRYPTED if states.pop() else ENCRYPTED
	else:                 # Mixed state
		return MIXED


def chalresp(challenge):
	resp = check_output(['ykchalresp', challenge]).decode().strip('\n')

	if len(resp) != 40:
		raise Exception("Invalid yubikey response")

	check_output("echo -e '\a' > /dev/console", shell=True)

	print("Yubikey sent a valid response")
	return resp


def unlock():
	password = chalresp(CHALLENGE)
	for device, disk in list(zip(DEVICES, DISKS)):
		print("Unlocking " + device + " as " +  disk)
		p = run(['cryptsetup', 'luksOpen', '-d', '-', device, disk], input=password, stdout=PIPE, encoding='ascii')
		if p.returncode != 0 and p.returncode != 5:
			raise Exception("LuksOpen return code: " + str(p.returncode))

def try_mount():
	if 'zfs' not in check_output('lsmod').decode():
		print("Loading ZFS module")
		print(check_output(['modprobe', 'zfs']))

	missing = False
	for pool in POOLS:
		if pool not in check_output(['zpool', 'list']).decode():
			print("Missing pool: " + pool)
			missing = True
			print("Mounting pool " + pool)
			check_output(["zpool", "import", pool])
	return missing


def main():
	post_script_started = False
	while True:
		if disks_encrypted() == ENCRYPTED or disks_encrypted() == MIXED:
			print("Disks encrypted")
			if yubikey_present():
				print("Unlocking")
				unlock()
				print("Done")
			else:
				print("Ubikey not found")
				sleep(3)

		else:
			if not try_mount():
				print("Disks okay")
				if not post_script_started:
					print("Running post-script")
					print(check_output(POST_SCRIPT_COMMAND))
                    post_script_started = True
				sleep(60 * 5)



if __name__ == "__main__":
	main()
