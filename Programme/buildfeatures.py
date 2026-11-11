"""Optional features provided by the modules bundled in this edition."""

try:
    import authorhtmlexport as author_html_export
except ModuleNotFoundError as error:
    if error.name != "authorhtmlexport":
        raise
    author_html_export = None
