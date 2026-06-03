import unittest

from keyboard_assistant.platform.startup import RUN_KEY, WindowsStartupManager


class FakeKey:
    def __init__(self, registry: "FakeRegistry") -> None:
        self.registry = registry

    def __enter__(self) -> "FakeKey":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class FakeRegistry:
    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def OpenKey(self, root: object, path: str, _reserved: int, _access: int) -> FakeKey:
        self._assert_key(root, path)
        return FakeKey(self)

    def CreateKeyEx(self, root: object, path: str, _reserved: int, _access: int) -> FakeKey:
        self._assert_key(root, path)
        return FakeKey(self)

    def QueryValueEx(self, _key: FakeKey, name: str) -> tuple[str, int]:
        if name not in self.values:
            raise OSError("missing value")
        return self.values[name], self.REG_SZ

    def SetValueEx(self, _key: FakeKey, name: str, _reserved: int, _value_type: int, value: str) -> None:
        self.values[name] = value

    def DeleteValue(self, _key: FakeKey, name: str) -> None:
        if name not in self.values:
            raise OSError("missing value")
        del self.values[name]

    def _assert_key(self, root: object, path: str) -> None:
        if root is not self.HKEY_CURRENT_USER or path != RUN_KEY:
            raise AssertionError("unexpected registry key")


class StartupTests(unittest.TestCase):
    def test_status_reports_unsupported_without_registry(self) -> None:
        manager = WindowsStartupManager(registry=None)
        status = manager.status()
        self.assertFalse(status.supported)
        self.assertFalse(status.enabled)

    def test_enable_status_disable_round_trip(self) -> None:
        registry = FakeRegistry()
        manager = WindowsStartupManager(registry=registry)

        self.assertFalse(manager.status().enabled)
        manager.enable("python -m keyboard_assistant.desktop")
        status = manager.status()
        self.assertTrue(status.supported)
        self.assertTrue(status.enabled)
        self.assertEqual(status.command, "python -m keyboard_assistant.desktop")

        manager.disable()
        self.assertFalse(manager.status().enabled)

    def test_enable_requires_command(self) -> None:
        manager = WindowsStartupManager(registry=FakeRegistry())
        with self.assertRaises(ValueError):
            manager.enable(" ")


if __name__ == "__main__":
    unittest.main()
