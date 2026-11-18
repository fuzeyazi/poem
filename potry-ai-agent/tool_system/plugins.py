"""内置工具插件热加载:扫描目录、按 mtime 载入/重载/卸载。"""
import importlib.util
import sys
from pathlib import Path


class PluginLoader:
    def __init__(self, plugin_dir: str | Path) -> None:
        self._dir = Path(plugin_dir)
        self._loaded: dict[str, tuple[int, str, list[str]]] = {}

    async def refresh(self, catalog) -> None:
        current: dict[str, int] = {}
        if self._dir.is_dir():
            for path in sorted(self._dir.glob("*.py")):
                if path.name.startswith("_"):
                    continue
                current[str(path.resolve())] = path.stat().st_mtime_ns

        for key in list(self._loaded):
            if key not in current:
                catalog.unregister_plugin(key)
                self._loaded.pop(key, None)
                print(f"[tools] plugin unload {Path(key).name}")

        for key, mtime in current.items():
            old = self._loaded.get(key)
            if old is not None and old[0] == mtime:
                continue
            if old is not None:
                catalog.unregister_plugin(key)
            module_name, names = self._load(key, mtime, catalog)
            # 失败也记 mtime,避免每次 get_tools 重复刷同样的错误
            self._loaded[key] = (mtime, module_name, names)

    def _load(self, key: str, mtime: int, catalog) -> tuple[str, list[str]]:
        path = Path(key)
        module_name = f"plugin_{path.stem}_{mtime}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise ImportError("无法创建模块规格")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if not callable(register):
                raise AttributeError("缺少 register(catalog) 函数")
            catalog.begin_plugin(key)
            try:
                register(catalog)
            finally:
                catalog.end_plugin()
            names = sorted(catalog.plugin_tool_names(key))
            print(f"[tools] plugin load {path.name}: {', '.join(names) or '(none)'}")
            return module_name, names
        except Exception as exc:  # noqa: BLE001 - 单个插件失败不影响其它工具
            catalog.unregister_plugin(key)
            sys.modules.pop(module_name, None)
            print(f"[tools] plugin fail {path.name}: {str(exc)[:200]}")
            return "", []
