# validators.py
from simpleeval import simple_eval, InvalidExpression
from django.core.exceptions import ValidationError
import math

# The maximum variable set any formula could ever see
# Use representative dummy values for validation purposes
FORMULA_DUMMY_CONTEXT = {
    'credits': 20,
    'students': 100,
    'contact': 40.0,
    'admin': 10.0,
    'contact_scaling': 2.5,
    'admin_scaling': 1.0,
    'assessment_scaling': 1.0,
}

# A list of permitted formula functions
FORMULA_FUNCTIONS = {
    'log': math.log,
    'log2': math.log2,
    'log10': math.log10,
    'sqrt': math.sqrt,
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
}

def validate_formula(value):
    """Validate that a formula string is safe and evaluable."""
    if not value:
        return
    try:
        result = simple_eval(
            value,
            names=FORMULA_DUMMY_CONTEXT,
            functions=FORMULA_FUNCTIONS,
        )
        if not isinstance(result, (int, float)):
            raise ValidationError("Formula must evaluate to a number.")
    except InvalidExpression as e:
        raise ValidationError(f"Invalid formula: {e}")
    except ZeroDivisionError:
        pass  # acceptable — dummy values may trigger this; real data might not
    except Exception as e:
        raise ValidationError(f"Formula error: {e}")

# ---------------------------------------------------------------------------
# Assessment resource files
#
# Uploads are refused only for types that are dangerous or never legitimate assessment
# material. Safety when viewing comes from assessment_file_serving() below: only a few
# types are ever shown in the browser, with a fixed content type; everything else downloads.
# ---------------------------------------------------------------------------

# Web pages and scripts that would run in a browser, and Windows executables and shortcuts
BLOCKED_UPLOAD_EXTENSIONS = {
    '.html', '.htm', '.xhtml', '.shtml', '.svg', '.svgz', '.js', '.mjs', '.xml', '.xsl',
    '.exe', '.com', '.bat', '.cmd', '.msi', '.msp', '.scr', '.pif', '.cpl', '.hta',
    '.vbs', '.vbe', '.jse', '.wsf', '.wsh', '.ps1', '.psm1', '.reg', '.lnk', '.url',
    '.jar', '.dll',
}

# Macro-enabled Office files: existing ones still download, but new ones are refused
MACRO_OFFICE_EXTENSIONS = {
    '.docm', '.dotm', '.xlsm', '.xltm', '.xlam', '.pptm', '.potm', '.ppsm', '.ppam',
}

# Types shown in the browser, with the content type to use. Anything else is a download.
# Code and data files are shown as plain text, so they display rather than run.
INLINE_CONTENT_TYPES = {
    '.pdf': 'application/pdf',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.bmp': 'image/bmp',
    '.mp4': 'video/mp4',
    '.mov': 'video/quicktime',
    '.txt': 'text/plain; charset=utf-8',
    '.csv': 'text/plain; charset=utf-8',
    '.py': 'text/plain; charset=utf-8',
    '.ipynb': 'text/plain; charset=utf-8',
    '.json': 'text/plain; charset=utf-8',
}


def file_extension(name):
    """The lower case extension of a file name, including the dot, or ''"""
    import os
    return os.path.splitext(name or '')[1].lower()


def validate_assessment_upload(upload):
    """Refuse dangerous, macro-enabled, or oversized assessment uploads."""
    from django.conf import settings

    extension = file_extension(upload.name)
    if extension in BLOCKED_UPLOAD_EXTENSIONS:
        raise ValidationError(
            f"{extension} files can't be uploaded, as they could run code. "
            "Please upload a PDF or another document format instead.")
    if extension in MACRO_OFFICE_EXTENSIONS:
        raise ValidationError(
            f"Macro-enabled files ({extension}) can't be uploaded. "
            "Please save the file without macros (e.g. as .docx, .xlsx or .pptx) and upload that.")

    max_mb = getattr(settings, 'WAM_ASSESSMENT_MAX_UPLOAD_MB', 50)
    if upload.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Files can be at most {max_mb} MB; this one is {upload.size / 1024 / 1024:.0f} MB.")


def assessment_file_serving(name):
    """
    How to serve an assessment file: (content_type, as_attachment).

    Only the types in INLINE_CONTENT_TYPES open in the browser, with that fixed type, so an
    uploaded web page or script (including any uploaded before uploads were restricted)
    is always a download and can't run inside WAM.
    """
    content_type = INLINE_CONTENT_TYPES.get(file_extension(name))
    if content_type:
        return content_type, False
    return 'application/octet-stream', True
