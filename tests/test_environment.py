import importlib


def test_project_dependencies_import():
    modules = [
        "requests",
        "pandas",
        "pyarrow",
        "duckdb",
        "dbt",
        "streamlit",
        "plotly",
        "google.transit.gtfs_realtime_pb2",
    ]

    for module_name in modules:
        importlib.import_module(module_name)
