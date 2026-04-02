import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def resolve_file_path(file_location: str):
    if not file_location:
        raise ValueError('file_location is required')
    path = Path(file_location)
    return path if path.is_absolute() else (ROOT / file_location).resolve()


def execute_python(data: dict):
    file_location = data.get('file_location')
    function_name = data.get('function_name')
    args = data.get('args', []) or []
    kwargs = data.get('kwargs', {}) or {}
    if not file_location or not function_name:
        return {'success': False, 'error': 'file_location and function_name are required'}
    module_path = resolve_file_path(file_location)
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        return {'success': False, 'error': 'unable to load python file'}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, function_name, None)
    if not callable(function):
        return {'success': False, 'error': f'function {function_name} not found'}
    result = function(*args, **kwargs)
    return {'success': True, 'result': result}
