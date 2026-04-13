#!/usr/bin/env python3
"""Generate docker-compose.yml and credentials for the Computer Networks lab."""

import argparse
import json
import os
import secrets
import string
import sys

import yaml


def generate_password(length=8):
    """Generate a random alphanumeric password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def validate_args(args):
    """Validate command-line arguments."""
    if args.num_students < 1:
        print("Error: Number of students must be at least 1.", file=sys.stderr)
        sys.exit(1)
    if args.num_students > 245:
        print("Error: Maximum 245 students (subnet limit).", file=sys.stderr)
        sys.exit(1)

    n = args.num_students
    ranges = {
        "SSH": (args.base_ssh, args.base_ssh + n - 1),
        "HTTP": (args.base_http, args.base_http + n - 1),
        "ttyd": (args.base_ttyd, args.base_ttyd + n - 1),
    }

    for name, (start, end) in ranges.items():
        if start < 1 or end > 65535:
            print(f"Error: {name} port range {start}-{end} out of valid range.", file=sys.stderr)
            sys.exit(1)

    range_list = list(ranges.items())
    for i in range(len(range_list)):
        for j in range(i + 1, len(range_list)):
            name_a, (start_a, end_a) = range_list[i]
            name_b, (start_b, end_b) = range_list[j]
            if start_a <= end_b and start_b <= end_a:
                print(
                    f"Error: {name_a} ports ({start_a}-{end_a}) overlap "
                    f"with {name_b} ports ({start_b}-{end_b}).",
                    file=sys.stderr,
                )
                sys.exit(1)


def generate_compose(args, passwords):
    """Build the docker-compose dictionary."""
    services = {}

    for i in range(1, args.num_students + 1):
        name = f"student{i:02d}"
        services[name] = {
            "build": ".",
            "container_name": name,
            "hostname": name,
            "environment": [f"STUDENT_PASSWORD={passwords[i - 1]}"],
            "ports": [
                f"{args.base_ssh + i - 1}:22",
                f"{args.base_http + i - 1}:80",
                f"{args.base_ttyd + i - 1}:7681",
            ],
            "networks": {
                "lab-network": {
                    "ipv4_address": f"172.20.0.{10 + i}",
                },
            },
            "cap_add": ["NET_ADMIN", "NET_RAW"],
            "mem_limit": "256m",
            "cpus": 0.5,
            "restart": "unless-stopped",
        }

    compose = {
        "services": services,
        "networks": {
            "lab-network": {
                "driver": "bridge",
                "ipam": {
                    "config": [{"subnet": "172.20.0.0/24"}],
                },
            },
        },
    }

    return compose


def write_credentials(students, args, output_dir):
    """Write credentials to TXT and JSON files."""
    txt_lines = []
    txt_lines.append("=" * 78)
    txt_lines.append("  COMPUTER NETWORKS LAB — STUDENT CREDENTIALS")
    txt_lines.append("=" * 78)
    txt_lines.append("")
    txt_lines.append(
        f"{'Student':<12} {'Password':<12} {'Terminal (ttyd)':<28} {'Website':<24} SSH"
    )
    txt_lines.append("-" * 78)

    json_data = []

    for i, (name, password) in enumerate(students):
        ssh_port = args.base_ssh + i
        http_port = args.base_http + i
        ttyd_port = args.base_ttyd + i

        txt_lines.append(
            f"{name:<12} {password:<12} http://<VPS_IP>:{ttyd_port:<10} "
            f"http://<VPS_IP>:{http_port:<7} ssh -p {ssh_port} student@<VPS_IP>"
        )

        json_data.append(
            {
                "student": name,
                "username": "student",
                "password": password,
                "ssh_port": ssh_port,
                "http_port": http_port,
                "ttyd_port": ttyd_port,
                "ip": f"172.20.0.{11 + i}",
            }
        )

    txt_lines.append("-" * 78)
    txt_lines.append("")
    txt_lines.append("Username for all students: student")
    txt_lines.append("Replace <VPS_IP> with your server's public IP address.")
    txt_lines.append("")

    txt_path = os.path.join(output_dir, "credentials.txt")
    json_path = os.path.join(output_dir, "credentials.json")

    with open(txt_path, "w") as f:
        f.write("\n".join(txt_lines))

    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)

    return txt_path, json_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate docker-compose.yml and credentials for the networks lab."
    )
    parser.add_argument(
        "-n",
        "--num-students",
        type=int,
        default=20,
        help="Number of students (default: 20)",
    )
    parser.add_argument(
        "-s",
        "--single-password",
        nargs="?",
        const="__generate__",
        default=None,
        help="Use a single shared password (optionally specify the password)",
    )
    parser.add_argument(
        "--base-ssh", type=int, default=2201, help="Base SSH port (default: 2201)"
    )
    parser.add_argument(
        "--base-http", type=int, default=8001, help="Base HTTP port (default: 8001)"
    )
    parser.add_argument(
        "--base-ttyd", type=int, default=7001, help="Base ttyd port (default: 7001)"
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="Output directory (default: current directory)",
    )

    args = parser.parse_args()
    validate_args(args)

    # Generate passwords
    if args.single_password is not None:
        if args.single_password == "__generate__":
            shared_password = generate_password()
        else:
            shared_password = args.single_password
        passwords = [shared_password] * args.num_students
    else:
        passwords = [generate_password() for _ in range(args.num_students)]

    # Build student list
    students = []
    for i in range(args.num_students):
        name = f"student{i + 1:02d}"
        students.append((name, passwords[i]))

    # Generate docker-compose.yml
    compose = generate_compose(args, passwords)
    compose_path = os.path.join(args.output_dir, "docker-compose.yml")
    with open(compose_path, "w") as f:
        yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

    # Generate credentials
    txt_path, json_path = write_credentials(students, args, args.output_dir)

    print(f"Generated {args.num_students} student containers:")
    print(f"  - {compose_path}")
    print(f"  - {txt_path}")
    print(f"  - {json_path}")
    print()
    print(f"  SSH ports:  {args.base_ssh}-{args.base_ssh + args.num_students - 1}")
    print(f"  HTTP ports: {args.base_http}-{args.base_http + args.num_students - 1}")
    print(f"  ttyd ports: {args.base_ttyd}-{args.base_ttyd + args.num_students - 1}")


if __name__ == "__main__":
    main()
