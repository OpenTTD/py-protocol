try:
    import beeline

    def traced(prefix):
        # The common case is to use the function-name, so automate this.
        def wrapper(func):
            return beeline.traced_impl(beeline.tracer, f"{prefix}.{func.__name__}", None, None)(func)

        return wrapper

    tracer = beeline.tracer
    untraced = beeline.untraced
    add_trace_field = beeline.add_trace_field

except ImportError:
    # Honeycomb Beeline package is not installed. Mock the tracer functions.

    def traced(prefix):
        def wrapper(func):
            return func

        return wrapper

    class tracer:
        def __init__(self, name):
            pass

        def __enter__(self):
            pass

        def __exit__(self, type, value, traceback):
            pass

    def untraced(func):
        return func

    def add_trace_field(key, value):
        pass
