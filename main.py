#!/usr/bin/env python3.7

# wacom-compatible area calculator
# copyright (c) 2021 emily geil

# requires xsetwacom

import argparse
import sys
import os
import subprocess

xsetwacom = "/usr/bin/xsetwacom"

def round2(num):
    return round(num + 0.1)

def get_devices():
    command = [
        xsetwacom,
        "--list",
        "devices"
    ]
    process = subprocess.run(command, capture_output=True)
    output = process.stdout.decode().split("\n")[:-1]
    if len(output) < 1:
        return None

    devices = {}
    for device in list(output):
        parts = device.split("\t")
        device_name = parts[0].strip()
        device_id = parts[1][4:].strip()
        device_type = parts[2][6:].strip()
        devices[device_id] = {
            "name": device_name,
            "type": device_type
        }

    return devices

def device_has_area(device):
    command = [
        xsetwacom,
        "--get",
        device,
        "Area"
    ]
    process = subprocess.run(command, capture_output=True)
    if process.stdout.decode().endswith("does not exist on device.\n"):
        return False
    area = process.stdout.decode()[:-1].split(" ")
    try:
        for coord in area:
            _ = int(coord)
        return True
    except:
        return False

def find_first_tablet():
    devices = get_devices()
    for device in devices:
        if devices[device]["type"] == "STYLUS":
            if device_has_area(device):
                return device
    for device in devices:
        if devices[device]["type"] == "PAD":
            if device_has_area(device):
                return device
    return None

def get_tablet_max_area(device, dry_run=False):
    if not dry_run:
        command = [
            xsetwacom,
            "--set",
            device,
            "Area",
            "-1 -1 -1 -1"
        ]
        process = subprocess.run(command, capture_output=False)
    else:
        print("WARNING: area calculations may be invalid -- dry run mode is enabled, could not set tablet to default area", file=sys.stderr)
        print("WARNING: use --device-area to manually specify the tablet area", file=sys.stderr)
    command = [
        xsetwacom,
        "--get",
        device,
        "Area"
    ]
    process = subprocess.run(command, capture_output=True)
    x1, y1, x2, y2 = process.stdout.decode()[:-1].split()
    if dry_run:
        if not (x1 == 0) or not (y1 == 0):
            print("ERROR: DETECTED INVALID DEVICE AREA, CALCULATIONS WILL NOT BE CORRECT!", file=sys.stderr)
            print("ERROR: USE --device-area TO MANUALLY SPECIFY THE DEVICE AREA", file=sys.stderr)
    return x2, y2

def convert_aspect(aspect):
    width, height = aspect.split(":")
    return float(width), float(height)

def convert_size(size):
    width, height = size.split("x")
    return float(width), float(height)

def set_area(device, x1, y1, x2, y2, verbose=False, dry_run=False):
    command = [
        xsetwacom,
        "--set",
        device,
        "Area",
        f"{x1} {y1} {x2} {y2}"
    ]
    if verbose:
        print(" ".join(command))
    if not dry_run:
        process = subprocess.run(command, capture_output=False)

def main():
    arg_parser = argparse.ArgumentParser(description="set wacom-compatible active area")
    arg_parser.add_argument("--device", type=str, help="the tablet device id or name")
    arg_parser.add_argument("--aspect", type=str, default="16:9", help="the aspect ratio of the screen (default 16:9)")
    arg_parser.add_argument("--device-area", type=str, help="the full area of the tablet in lines")
    arg_parser.add_argument("--device-resolution", type=int, default=2540, help="the resolution of the tablet in lines per inch (default 2540)")
    arg_parser.add_argument("--width", type=float, help="the desired width of the active area")
    arg_parser.add_argument("--height", type=float, help="the desired height of the active area")
    arg_parser.add_argument("--unit", type=str, choices=["in", "cm", "mm", "lines"], default="mm", help="unit for desired width/height (default mm)")
    arg_parser.add_argument("--full", action="store_true", help="use the full active area (adjusting for aspect ratio)")
    arg_parser.add_argument("--align", type=str, choices=["topleft", "top", "topright", "left", "center", "right", "bottomleft", "bottom", "bottomright"], default="center", help="where to align the active area on the tablet (default center)")
    arg_parser.add_argument("-v", action="store_true", help="use verbose output")
    arg_parser.add_argument("--dry-run", action="store_true", help="do not perform any action on tablets")
    args = arg_parser.parse_args()

    # check if xsetwacom exists
    if not os.path.exists(xsetwacom):
        sys.exit(f"{xsetwacom} not found")

    # verify arguments
    incompatible_args = [["width", "height", "full"]]
    args_dict = vars(args)
    for incompatible_group in incompatible_args:
        found_args = []
        for arg in incompatible_group:
            if isinstance(args_dict[arg], float) or (args_dict[arg] == True):
                found_args.append(arg)
            if len(found_args) > 1:
                sys.exit(f"the following arguments may not be used together: {', '.join(found_args)}")
        if len(found_args) == 0:
            sys.exit(f"exactly one of the following arguments must be specified: {', '.join(incompatible_group)}")

    # check or set tablet device id
    if args.device is None:
        args.device = find_first_tablet()
    if args.device is None:
        sys.exit("could not find tablet")
    if not device_has_area(args.device):
        sys.exit(f"invalid tablet device id: {args.device}")

    # validate aspect ratio
    try:
        width, height = args.aspect.split(":")
        _ = int(width)
        _ = int(height)
    except:
        sys.exit(f"invalid screen aspect ratio: {args.aspect}")

    # check or set tablet area
    if args.device_area is not None:
        try:
            for size in args.device_area.split("x"):
                _ = int(size)
        except:
            sys.exit(f"invalid device area: {args.device_area}")
    else:
        args.device_area = "x".join(get_tablet_max_area(args.device, dry_run=args.dry_run))



    # convert area into lines, if necessary
    if not args.full:
        if not args.unit == "lines":
            if args.unit == "in":
                divisor = 1
            elif args.unit == "cm":
                divisor = 2.54
            elif args.unit == "mm":
                divisor = 25.4
                
            if args.width is not None:
                args.width /= divisor
                args.width *= args.device_resolution
            else:
                args.height /= divisor
                args.height *= args.device_resolution
    args.unit = "lines"

    # calculate size
    screen_width, screen_height = convert_aspect(args.aspect)
    tablet_width, tablet_height = convert_size(args.device_area)
    if args.full:
        if (screen_width / screen_height) > (tablet_width / tablet_height): # screen is wider than area, dead area will be on top/bottom
            args.width = tablet_width
            args.height = (args.width * (screen_height / screen_width))
        elif (screen_width / screen_height) < (tablet_width / tablet_height):   # screen is taller than area, dead area will be on sides
            args.height = tablet_height
            args.width = (args.height * (screen_width / screen_height))
        else:   # screen is the same aspect as tablet
            args.width = tablet_width
            args.height = tablet_height
    else:
        if args.width is None:
            args.width = (args.height * (screen_width / screen_height))
        elif args.height is None:
            args.height = (args.width * (screen_height / screen_width))

    # calculate offset (x1/y1), if necessary
    offset_x = 0
    offset_y = 0
    if not args.align == "topleft":
        x_center_offset = ((tablet_width / 2) - (args.width / 2))
        x_full_offset = (tablet_width - args.width)
        y_center_offset = ((tablet_height / 2) - (args.height / 2))
        y_full_offset = (tablet_height - args.height)
        if args.align == "top":
            offset_x = x_center_offset
        elif args.align == "topright":
            offset_x = x_full_offset
        elif args.align == "left":
            offset_y = y_center_offset
        elif args.align == "center":
            offset_x = x_center_offset
            offset_y = y_center_offset
        elif args.align == "right":
            offset_x = x_full_offset
            offset_y = y_center_offset
        elif args.align == "bottomleft":
            offset_y = y_full_offset
        elif args.align == "bottom":
            offset_x = x_center_offset
            offset_y = y_full_offset
        elif args.align == "bottomright":
            offset_x = x_full_offset
            offset_y = y_full_offset

    # calculate x2/y2
    x2 = offset_x + args.width
    y2 = offset_y + args.height
    if round2(x2) > round2(tablet_width):
        sys.exit("area width is greater than tablet size!")
    if round2(y2) > round2(tablet_height):
        sys.exit("area height is greater than tablet size!")

    # set area
    set_area(args.device, round2(offset_x), round2(offset_y), round2(x2), round2(y2), verbose=args.v, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
