"""pdf-reader implementation package.

Layering (one-way only, never reversed):

    util -> config -> endpoint -> plan -> run -> deliver -> cli

``plan`` decides *what* to do and has no side effects; ``run`` is the only layer
that performs I/O against the endpoint; ``deliver`` only converts the server's
product into our on-disk shape.
"""
