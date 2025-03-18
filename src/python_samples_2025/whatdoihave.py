import importlib
import pkgutil

# Verificar los módulos disponibles
print("Módulos disponibles en haystack.components.audio:")
try:
    import haystack.components.audio
    for _, name, is_pkg in pkgutil.iter_modules(haystack.components.audio.__path__):
        print(f"- {name} ({'package' if is_pkg else 'module'})")
    
    print("\nClases disponibles en haystack.components.audio:")
    for module_info in pkgutil.iter_modules(haystack.components.audio.__path__):
        module_name = module_info.name
        full_path = f"haystack.components.audio.{module_name}"
        try:
            module = importlib.import_module(full_path)
            for attr_name in dir(module):
                if attr_name.startswith('_'):
                    continue
                attr = getattr(module, attr_name)
                if isinstance(attr, type):
                    print(f"- {full_path}.{attr_name}")
        except ImportError as e:
            print(f"Error importando {full_path}: {e}")
except ImportError as e:
    print(f"Error: {e}")

print("\nVersión de haystack-ai:")
try:
    import haystack
    print(haystack.__version__)
except (ImportError, AttributeError) as e:
    print(f"Error: {e}")