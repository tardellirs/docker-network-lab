"""Tests for generate_lab.py — validates docker-compose.yml and credentials generation."""

import json
import os
import subprocess
import sys

import pytest
import yaml

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "generate_lab.py")


def run_generate(tmp_path, extra_args=None):
    """Run generate_lab.py in a temp directory and return parsed outputs."""
    args = [sys.executable, SCRIPT, "-o", str(tmp_path)]
    if extra_args:
        args.extend(extra_args)
    result = subprocess.run(args, capture_output=True, text=True)
    return result


def load_compose(tmp_path):
    with open(tmp_path / "docker-compose.yml") as f:
        return yaml.safe_load(f)


def load_credentials_json(tmp_path):
    with open(tmp_path / "credentials.json") as f:
        return json.load(f)


# --- Generation and structure ---


class TestBasicGeneration:
    def test_default_generates_20_students(self, tmp_path):
        result = run_generate(tmp_path)
        assert result.returncode == 0
        compose = load_compose(tmp_path)
        assert len(compose["services"]) == 20

    def test_custom_student_count(self, tmp_path):
        run_generate(tmp_path, ["-n", "5"])
        compose = load_compose(tmp_path)
        assert len(compose["services"]) == 5

    def test_single_student(self, tmp_path):
        run_generate(tmp_path, ["-n", "1"])
        compose = load_compose(tmp_path)
        assert len(compose["services"]) == 1
        assert "student01" in compose["services"]

    def test_creates_all_output_files(self, tmp_path):
        run_generate(tmp_path, ["-n", "3"])
        assert (tmp_path / "docker-compose.yml").exists()
        assert (tmp_path / "credentials.txt").exists()
        assert (tmp_path / "credentials.json").exists()


# --- Password handling ---


class TestPasswords:
    def test_unique_passwords_by_default(self, tmp_path):
        run_generate(tmp_path, ["-n", "10"])
        creds = load_credentials_json(tmp_path)
        passwords = [c["password"] for c in creds]
        assert len(set(passwords)) == 10

    def test_single_password_flag(self, tmp_path):
        run_generate(tmp_path, ["-n", "5", "-s"])
        creds = load_credentials_json(tmp_path)
        passwords = [c["password"] for c in creds]
        assert len(set(passwords)) == 1

    def test_single_password_with_value(self, tmp_path):
        run_generate(tmp_path, ["-n", "5", "-s", "testpass123"])
        creds = load_credentials_json(tmp_path)
        for c in creds:
            assert c["password"] == "testpass123"

    def test_password_in_compose_matches_credentials(self, tmp_path):
        run_generate(tmp_path, ["-n", "3"])
        compose = load_compose(tmp_path)
        creds = load_credentials_json(tmp_path)
        for c in creds:
            service = compose["services"][c["student"]]
            env_password = None
            for env in service["environment"]:
                if env.startswith("STUDENT_PASSWORD="):
                    env_password = env.split("=", 1)[1]
            assert env_password == c["password"]


# --- Port mapping ---


class TestPorts:
    def test_default_port_mapping(self, tmp_path):
        run_generate(tmp_path, ["-n", "3"])
        compose = load_compose(tmp_path)

        s1 = compose["services"]["student01"]
        assert "2201:22" in s1["ports"]
        assert "8001:80" in s1["ports"]
        assert "7001:7681" in s1["ports"]

        s3 = compose["services"]["student03"]
        assert "2203:22" in s3["ports"]
        assert "8003:80" in s3["ports"]
        assert "7003:7681" in s3["ports"]

    def test_custom_base_ports(self, tmp_path):
        run_generate(tmp_path, ["-n", "2", "--base-ssh", "3000", "--base-http", "9000", "--base-ttyd", "6000"])
        compose = load_compose(tmp_path)

        s1 = compose["services"]["student01"]
        assert "3000:22" in s1["ports"]
        assert "9000:80" in s1["ports"]
        assert "6000:7681" in s1["ports"]

        s2 = compose["services"]["student02"]
        assert "3001:22" in s2["ports"]
        assert "9001:80" in s2["ports"]
        assert "6001:7681" in s2["ports"]

    def test_port_in_credentials_json(self, tmp_path):
        run_generate(tmp_path, ["-n", "2"])
        creds = load_credentials_json(tmp_path)
        assert creds[0]["ssh_port"] == 2201
        assert creds[0]["http_port"] == 8001
        assert creds[0]["ttyd_port"] == 7001
        assert creds[1]["ssh_port"] == 2202


# --- Network configuration ---


class TestNetwork:
    def test_bridge_network_with_subnet(self, tmp_path):
        run_generate(tmp_path, ["-n", "2"])
        compose = load_compose(tmp_path)
        network = compose["networks"]["lab-network"]
        assert network["driver"] == "bridge"
        assert network["ipam"]["config"][0]["subnet"] == "172.20.0.0/24"

    def test_static_ips(self, tmp_path):
        run_generate(tmp_path, ["-n", "3"])
        compose = load_compose(tmp_path)
        assert compose["services"]["student01"]["networks"]["lab-network"]["ipv4_address"] == "172.20.0.11"
        assert compose["services"]["student02"]["networks"]["lab-network"]["ipv4_address"] == "172.20.0.12"
        assert compose["services"]["student03"]["networks"]["lab-network"]["ipv4_address"] == "172.20.0.13"

    def test_ip_in_credentials_json(self, tmp_path):
        run_generate(tmp_path, ["-n", "2"])
        creds = load_credentials_json(tmp_path)
        assert creds[0]["ip"] == "172.20.0.11"
        assert creds[1]["ip"] == "172.20.0.12"


# --- Container configuration ---


class TestContainerConfig:
    def test_capabilities(self, tmp_path):
        run_generate(tmp_path, ["-n", "2"])
        compose = load_compose(tmp_path)
        for name, service in compose["services"].items():
            assert "NET_ADMIN" in service["cap_add"]
            assert "NET_RAW" in service["cap_add"]

    def test_resource_limits(self, tmp_path):
        run_generate(tmp_path, ["-n", "2"])
        compose = load_compose(tmp_path)
        for name, service in compose["services"].items():
            assert service["mem_limit"] == "256m"
            assert service["cpus"] == 0.5

    def test_hostnames(self, tmp_path):
        run_generate(tmp_path, ["-n", "3"])
        compose = load_compose(tmp_path)
        assert compose["services"]["student01"]["hostname"] == "student01"
        assert compose["services"]["student02"]["hostname"] == "student02"
        assert compose["services"]["student03"]["hostname"] == "student03"

    def test_container_names(self, tmp_path):
        run_generate(tmp_path, ["-n", "2"])
        compose = load_compose(tmp_path)
        assert compose["services"]["student01"]["container_name"] == "student01"
        assert compose["services"]["student02"]["container_name"] == "student02"

    def test_restart_policy(self, tmp_path):
        run_generate(tmp_path, ["-n", "1"])
        compose = load_compose(tmp_path)
        assert compose["services"]["student01"]["restart"] == "unless-stopped"

    def test_build_context(self, tmp_path):
        run_generate(tmp_path, ["-n", "1"])
        compose = load_compose(tmp_path)
        assert compose["services"]["student01"]["build"] == "."


# --- Credentials files ---


class TestCredentials:
    def test_credentials_txt_contains_all_students(self, tmp_path):
        run_generate(tmp_path, ["-n", "5"])
        txt = (tmp_path / "credentials.txt").read_text()
        for i in range(1, 6):
            assert f"student{i:02d}" in txt

    def test_credentials_json_structure(self, tmp_path):
        run_generate(tmp_path, ["-n", "3"])
        creds = load_credentials_json(tmp_path)
        assert len(creds) == 3
        for c in creds:
            assert "student" in c
            assert "username" in c
            assert c["username"] == "student"
            assert "password" in c
            assert "ssh_port" in c
            assert "http_port" in c
            assert "ttyd_port" in c
            assert "ip" in c

    def test_credentials_txt_mentions_student(self, tmp_path):
        run_generate(tmp_path, ["-n", "2"])
        txt = (tmp_path / "credentials.txt").read_text()
        assert "student" in txt


# --- Idempotency ---


class TestIdempotency:
    def test_running_twice_overwrites(self, tmp_path):
        run_generate(tmp_path, ["-n", "3", "-s", "fixedpass"])
        compose1 = (tmp_path / "docker-compose.yml").read_text()
        creds1 = (tmp_path / "credentials.json").read_text()

        run_generate(tmp_path, ["-n", "3", "-s", "fixedpass"])
        compose2 = (tmp_path / "docker-compose.yml").read_text()
        creds2 = (tmp_path / "credentials.json").read_text()

        assert compose1 == compose2
        assert creds1 == creds2


# --- Validation / error handling ---


class TestValidation:
    def test_zero_students_fails(self, tmp_path):
        result = run_generate(tmp_path, ["-n", "0"])
        assert result.returncode != 0

    def test_negative_students_fails(self, tmp_path):
        result = run_generate(tmp_path, ["-n", "-1"])
        assert result.returncode != 0

    def test_too_many_students_fails(self, tmp_path):
        result = run_generate(tmp_path, ["-n", "300"])
        assert result.returncode != 0

    def test_overlapping_ports_fails(self, tmp_path):
        # SSH starts at 7001, overlaps with ttyd default at 7001
        result = run_generate(tmp_path, ["-n", "5", "--base-ssh", "7001"])
        assert result.returncode != 0


# --- Zero-padding ---


class TestZeroPadding:
    def test_single_digit_padded(self, tmp_path):
        run_generate(tmp_path, ["-n", "9"])
        compose = load_compose(tmp_path)
        assert "student01" in compose["services"]
        assert "student09" in compose["services"]

    def test_double_digit_names(self, tmp_path):
        run_generate(tmp_path, ["-n", "12"])
        compose = load_compose(tmp_path)
        assert "student10" in compose["services"]
        assert "student12" in compose["services"]
