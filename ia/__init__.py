def __getattr__(name):
    if name == "executar":
        from .gateway import executar

        return executar
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
