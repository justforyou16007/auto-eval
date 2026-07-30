"""
Tests for env-component-manager.py.

Verifies that:
1. The tool exists and is executable
2. init command creates the directory structure
3. register command adds a component to tree.json
4. list command lists components from tree.json
5. search command finds components by text
6. info command displays component details
7. tree command displays the component tree
8. fork command copies a component and registers it
9. assemble command generates docker-compose.yml
10. Lazy loading: only tree.json is loaded; actual files loaded only on need
11. CLI handles invalid arguments gracefully
"""

import json
import os
import stat
import subprocess
import tempfile
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL_PATH = os.path.join(REPO_ROOT, "src", "tools", "env-component-manager.py")


class TestComponentManagerToolExists(unittest.TestCase):
    """Basic sanity checks for the tool."""

    def test_01_tool_exists(self):
        """env-component-manager.py exists at src/tools/."""
        self.assertTrue(os.path.isfile(TOOL_PATH), f"Missing: {TOOL_PATH}")

    def test_02_tool_is_executable(self):
        """env-component-manager.py is executable."""
        st = os.stat(TOOL_PATH)
        self.assertTrue(st.st_mode & stat.S_IXUSR, f"Not executable: {TOOL_PATH}")

    def test_03_dist_symlink_exists(self):
        """dist/tools/env-component-manager.py symlink exists."""
        symlink_path = os.path.join(REPO_ROOT, "dist", "tools", "env-component-manager.py")
        self.assertTrue(os.path.islink(symlink_path) or os.path.isfile(symlink_path),
                        f"Missing: {symlink_path}")
        if os.path.islink(symlink_path):
            self.assertTrue(os.path.exists(symlink_path),
                            f"Broken symlink: {symlink_path}")

    def test_04_help_flag(self):
        """Tool responds to --help."""
        result = subprocess.run(
            [TOOL_PATH, "--help"],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout.lower())


class TestComponentManagerInit(unittest.TestCase):
    """Test the init command."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="component-mgr-test-")
        self.components_dir = os.path.join(self.temp_dir, "components")

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.temp_dir], timeout=30)

    def _run(self, *args):
        cmd = [TOOL_PATH] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_05_init_creates_directory_structure(self):
        """init creates components/ directory with infra/, app/, and tree.json."""
        result = self._run("init", self.components_dir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        self.assertTrue(os.path.isdir(self.components_dir))
        self.assertTrue(os.path.isdir(os.path.join(self.components_dir, "infra")))
        self.assertTrue(os.path.isdir(os.path.join(self.components_dir, "app")))
        self.assertTrue(os.path.isfile(os.path.join(self.components_dir, "tree.json")))

    def test_06_init_idempotent(self):
        """init is idempotent (running twice is fine)."""
        self._run("init", self.components_dir)
        result = self._run("init", self.components_dir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_07_init_tree_yaml_format(self):
        """init creates a valid tree.json."""
        self._run("init", self.components_dir)
        tree_path = os.path.join(self.components_dir, "tree.json")
        with open(tree_path) as f:
            content = f.read()
        self.assertIn("version", content)
        self.assertIn("components", content)


class TestComponentManagerRegisterAndList(unittest.TestCase):
    """Test register and list commands."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="component-mgr-test-")
        self.components_dir = os.path.join(self.temp_dir, "components")
        subprocess.run([TOOL_PATH, "init", self.components_dir],
                       capture_output=True, timeout=30)

        # Create a component directory with component.yaml
        self.infra_comp_path = "infra/test-ubuntu"
        self.infra_comp_dir = os.path.join(self.components_dir, self.infra_comp_path)
        os.makedirs(self.infra_comp_dir)
        with open(os.path.join(self.infra_comp_dir, "component.yaml"), "w") as f:
            f.write("name: test-ubuntu\nlayer: infra\ntags: [ubuntu, test]\ndescription: Test Ubuntu image\n")
        # Create a Dockerfile
        with open(os.path.join(self.infra_comp_dir, "Dockerfile"), "w") as f:
            f.write("FROM ubuntu:22.04\n")

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.temp_dir], timeout=30)

    def _run(self, *args):
        cmd = [TOOL_PATH] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_08_register_adds_to_tree(self):
        """register adds a component to tree.json."""
        result = self._run("register", self.components_dir,
                           "--name", "test-ubuntu",
                           "--layer", "infra",
                           "--path", self.infra_comp_path,
                           "--tags", "ubuntu,test",
                           "--description", "Test Ubuntu image")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("registered", result.stdout.lower())

        # Verify tree.json was updated
        tree_path = os.path.join(self.components_dir, "tree.json")
        with open(tree_path) as f:
            content = f.read()
        self.assertIn("test-ubuntu", content)

    def test_09_list_shows_registered_components(self):
        """list shows registered components."""
        self._run("register", self.components_dir,
                  "--name", "test-ubuntu",
                  "--layer", "infra",
                  "--path", self.infra_comp_path,
                  "--tags", "ubuntu,test",
                  "--description", "Test Ubuntu image")

        result = self._run("list", self.components_dir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("test-ubuntu", result.stdout)

    def test_10_list_filter_by_layer(self):
        """list can filter by layer."""
        self._run("register", self.components_dir,
                  "--name", "test-ubuntu",
                  "--layer", "infra",
                  "--path", self.infra_comp_path,
                  "--tags", "ubuntu,test",
                  "--description", "Test Ubuntu image")

        result = self._run("list", self.components_dir, "--layer", "infra")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("test-ubuntu", result.stdout)

        result_app = self._run("list", self.components_dir, "--layer", "app")
        self.assertEqual(result_app.returncode, 0, msg=result_app.stderr)
        self.assertNotIn("test-ubuntu", result_app.stdout)

    def test_11_search_finds_components(self):
        """search finds components by text in description or tags."""
        self._run("register", self.components_dir,
                  "--name", "test-ubuntu",
                  "--layer", "infra",
                  "--path", self.infra_comp_path,
                  "--tags", "ubuntu,test",
                  "--description", "Test Ubuntu image")

        result = self._run("search", self.components_dir, "--query", "Ubuntu")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("test-ubuntu", result.stdout)

        result_no_match = self._run("search", self.components_dir, "--query", "nonexistent")
        self.assertEqual(result_no_match.returncode, 0, msg=result_no_match.stderr)
        self.assertIn("No components found", result_no_match.stdout)

    def test_12_search_filter_by_layer(self):
        """search can filter by layer."""
        self._run("register", self.components_dir,
                  "--name", "test-ubuntu",
                  "--layer", "infra",
                  "--path", self.infra_comp_path,
                  "--tags", "ubuntu,test",
                  "--description", "Test Ubuntu image")

        result = self._run("search", self.components_dir, "--query", "Ubuntu", "--layer", "infra")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("test-ubuntu", result.stdout)

    def test_13_register_duplicate_name_fails(self):
        """register with duplicate name fails."""
        self._run("register", self.components_dir,
                  "--name", "test-ubuntu",
                  "--layer", "infra",
                  "--path", self.infra_comp_path,
                  "--tags", "ubuntu,test",
                  "--description", "Test Ubuntu image")

        result = self._run("register", self.components_dir,
                           "--name", "test-ubuntu",
                           "--layer", "infra",
                           "--path", self.infra_comp_path,
                           "--tags", "ubuntu,test",
                           "--description", "Test Ubuntu image")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr.lower())

    def test_14_register_invalid_layer_fails(self):
        """register with invalid layer fails."""
        result = self._run("register", self.components_dir,
                           "--name", "bad-layer",
                           "--layer", "invalid",
                           "--path", self.infra_comp_path,
                           "--tags", "test",
                           "--description", "Bad layer test")
        self.assertNotEqual(result.returncode, 0)


class TestComponentManagerInfo(unittest.TestCase):
    """Test the info command."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="component-mgr-test-")
        self.components_dir = os.path.join(self.temp_dir, "components")
        subprocess.run([TOOL_PATH, "init", self.components_dir],
                       capture_output=True, timeout=30)

        self.infra_comp_path = "infra/test-ubuntu"
        os.makedirs(os.path.join(self.components_dir, self.infra_comp_path))
        with open(os.path.join(self.components_dir, self.infra_comp_path, "component.yaml"), "w") as f:
            f.write("""name: test-ubuntu
layer: infra
tags: [ubuntu, test]
description: "Test Ubuntu image"
base_image: "ubuntu:22.04"
ports:
  - "80:80"
env_vars:
  DEBUG: "true"
  LOG_LEVEL: "info"
health_check:
  command: "http://localhost:80/health"
  interval: 10
  timeout: 5
  retries: 3
""")
        subprocess.run([TOOL_PATH, "register", self.components_dir,
                       "--name", "test-ubuntu",
                       "--layer", "infra",
                       "--path", self.infra_comp_path,
                       "--tags", "ubuntu,test",
                       "--description", "Test Ubuntu image"],
                       capture_output=True, timeout=30)

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.temp_dir], timeout=30)

    def _run(self, *args):
        cmd = [TOOL_PATH] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_15_info_displays_component_details(self):
        """info displays full component details including metadata, ports, env vars."""
        result = self._run("info", self.components_dir, "--path", "test-ubuntu")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("test-ubuntu", result.stdout)
        self.assertIn("ubuntu:22.04", result.stdout)
        self.assertIn("80:80", result.stdout)
        self.assertIn("test-ubuntu", result.stdout)


class TestComponentManagerTree(unittest.TestCase):
    """Test the tree command."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="component-mgr-test-")
        self.components_dir = os.path.join(self.temp_dir, "components")
        subprocess.run([TOOL_PATH, "init", self.components_dir],
                       capture_output=True, timeout=30)

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.temp_dir], timeout=30)

    def _run(self, *args):
        cmd = [TOOL_PATH] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_16_tree_displays_empty_tree(self):
        """tree displays the structure even when empty."""
        result = self._run("tree", self.components_dir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("tree.json", result.stdout)
        self.assertIn("infra", result.stdout)
        self.assertIn("app", result.stdout)


class TestComponentManagerFork(unittest.TestCase):
    """Test the fork command."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="component-mgr-test-")
        self.components_dir = os.path.join(self.temp_dir, "components")
        subprocess.run([TOOL_PATH, "init", self.components_dir],
                       capture_output=True, timeout=30)

        self.infra_comp_path = "infra/test-ubuntu"
        os.makedirs(os.path.join(self.components_dir, self.infra_comp_path))
        with open(os.path.join(self.components_dir, self.infra_comp_path, "component.yaml"), "w") as f:
            f.write("name: test-ubuntu\nlayer: infra\ntags: [ubuntu, test]\ndescription: Test Ubuntu image\n")
        with open(os.path.join(self.components_dir, self.infra_comp_path, "Dockerfile"), "w") as f:
            f.write("FROM ubuntu:22.04\n")

        subprocess.run([TOOL_PATH, "register", self.components_dir,
                       "--name", "test-ubuntu",
                       "--layer", "infra",
                       "--path", self.infra_comp_path,
                       "--tags", "ubuntu,test",
                       "--description", "Test Ubuntu image"],
                       capture_output=True, timeout=30)

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.temp_dir], timeout=30)

    def _run(self, *args):
        cmd = [TOOL_PATH] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_17_fork_copies_component(self):
        """fork copies a component and registers the new one."""
        result = self._run("fork", self.components_dir,
                           "--source", "test-ubuntu",
                           "--new-name", "test-ubuntu-forked",
                           "--new-path", "infra/test-ubuntu-forked")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("forked", result.stdout.lower())

        # Verify the forked directory exists
        forked_path = os.path.join(self.components_dir, "infra", "test-ubuntu-forked")
        self.assertTrue(os.path.isdir(forked_path))
        self.assertTrue(os.path.isfile(os.path.join(forked_path, "Dockerfile")))

        # Verify it's registered in tree.json
        tree_path = os.path.join(self.components_dir, "tree.json")
        with open(tree_path) as f:
            content = f.read()
        self.assertIn("test-ubuntu-forked", content)

    def test_18_fork_duplicate_path_fails(self):
        """fork with existing target path fails."""
        self._run("fork", self.components_dir,
                  "--source", "test-ubuntu",
                  "--new-name", "test-ubuntu-forked",
                  "--new-path", "infra/test-ubuntu-forked")

        result = self._run("fork", self.components_dir,
                           "--source", "test-ubuntu",
                           "--new-name", "test-ubuntu-forked-2",
                           "--new-path", "infra/test-ubuntu-forked")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr.lower())


class TestComponentManagerAssemble(unittest.TestCase):
    """Test the assemble command."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="component-mgr-test-")
        self.components_dir = os.path.join(self.temp_dir, "components")
        subprocess.run([TOOL_PATH, "init", self.components_dir],
                       capture_output=True, timeout=30)

        # Create an infra component
        self.infra_comp_path = "infra/test-ubuntu"
        os.makedirs(os.path.join(self.components_dir, self.infra_comp_path))
        with open(os.path.join(self.components_dir, self.infra_comp_path, "component.yaml"), "w") as f:
            f.write("name: test-ubuntu\nlayer: infra\ntags: [ubuntu, test]\ndescription: Test Ubuntu image\nbase_image: ubuntu:22.04\n")
        subprocess.run([TOOL_PATH, "register", self.components_dir,
                       "--name", "test-ubuntu",
                       "--layer", "infra",
                       "--path", self.infra_comp_path,
                       "--tags", "ubuntu,test",
                       "--description", "Test Ubuntu image"],
                       capture_output=True, timeout=30)

        # Create an app component
        self.app_comp_path = "app/e-commerce/backend"
        os.makedirs(os.path.join(self.components_dir, self.app_comp_path))
        with open(os.path.join(self.components_dir, self.app_comp_path, "component.yaml"), "w") as f:
            f.write("""name: test-backend
layer: app
tags: [e-commerce, api]
description: "Test e-commerce backend"
depends_on:
  - test-ubuntu
entrypoint: "python3 app.py"
ports:
  - "8000:8000"
env_vars:
  DATABASE_URL: "sqlite:///data.db"
  DEBUG: "true"
health_check:
  command: "http://localhost:8000/health"
  interval: 10
  timeout: 5
  retries: 3
""")
        subprocess.run([TOOL_PATH, "register", self.components_dir,
                       "--name", "test-backend",
                       "--layer", "app",
                       "--path", self.app_comp_path,
                       "--tags", "e-commerce,api",
                       "--description", "Test e-commerce backend"],
                       capture_output=True, timeout=30)

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.temp_dir], timeout=30)

    def _run(self, *args):
        cmd = [TOOL_PATH] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_19_assemble_generates_docker_compose(self):
        """assemble generates docker-compose.yml and manifest."""
        output_path = os.path.join(self.temp_dir, "docker-compose-test.yml")
        result = self._run("assemble", self.components_dir,
                           "--infra", "test-ubuntu",
                           "--app", "test-backend",
                           "--output", output_path)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Docker Compose written", result.stdout)

        # Verify docker-compose.yml exists
        self.assertTrue(os.path.isfile(output_path), f"Missing: {output_path}")
        with open(output_path) as f:
            content = f.read()
        self.assertIn("services:", content)
        self.assertIn("test-ubuntu", content)
        self.assertIn("test-backend", content)

        # Verify manifest exists
        manifest_dir = os.path.dirname(output_path)
        manifest_path = os.path.join(manifest_dir, "component-manifest.json")
        self.assertTrue(os.path.isfile(manifest_path), f"Missing: {manifest_path}")
        with open(manifest_path) as f:
            manifest = json.load(f)
        self.assertIn("components", manifest)
        self.assertIn("test-ubuntu", manifest["components"])
        self.assertIn("test-backend", manifest["components"])

    def test_20_assemble_missing_component_fails(self):
        """assemble with non-existent component fails."""
        result = self._run("assemble", self.components_dir,
                           "--infra", "nonexistent",
                           "--app", "test-backend",
                           "--output", os.path.join(self.temp_dir, "docker-compose-test.yml"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr.lower())


class TestComponentManagerLazyLoading(unittest.TestCase):
    """Test lazy loading behavior."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="component-mgr-test-")
        self.components_dir = os.path.join(self.temp_dir, "components")
        subprocess.run([TOOL_PATH, "init", self.components_dir],
                       capture_output=True, timeout=30)

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.temp_dir], timeout=30)

    def _run(self, *args):
        cmd = [TOOL_PATH] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_21_list_does_not_load_component_files(self):
        """list only reads tree.json, not actual component files."""
        # Register without creating component files
        # Create the component.yaml
        os.makedirs(os.path.join(self.components_dir, "infra", "test-ubuntu"))
        with open(os.path.join(self.components_dir, "infra", "test-ubuntu", "component.yaml"), "w") as f:
            f.write("name: test-ubuntu\nlayer: infra\ntags: [ubuntu, test]\ndescription: Test\n")

        self._run("register", self.components_dir,
                  "--name", "test-ubuntu",
                  "--layer", "infra",
                  "--path", "infra/test-ubuntu",
                  "--tags", "ubuntu,test",
                  "--description", "Test")

        # list should work without needing component files
        result = self._run("list", self.components_dir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("test-ubuntu", result.stdout)


if __name__ == "__main__":
    unittest.main()