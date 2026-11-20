"""
Import hours per person for many modules at once, from a spreadsheet.

Admin staff paste cells copied from a spreadsheet, or upload a .csv or .xlsx file, with a row per
person per module:

    Module code | Staff member | Contact hours | Assessment hours | Admin hours

A header row is optional; when there is one, columns are found by name, in any order. People can be
given by name ("Ann Lee", "Lee, Ann", "Dr Ann Lee", "A. Lee"), username, email address or staff number.

Each module's rows become a Plan (see hours_converter), previewed together. Modules with any problem
are left out, and listed with their problems; the rest are saved together when confirmed.
"""
import csv
import hashlib
import io
import json
import re
from decimal import Decimal, InvalidOperation

from .hours_converter import CATEGORIES, Plan

MAX_ROWS = 5000
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# What a header cell may say for each column (matched case-insensitively, as a start of the cell)
HEADERS = {
    'module': ('module', 'code'),
    'person': ('staff', 'person', 'name', 'lecturer', 'username', 'email', 'member'),
    'contact': ('contact', 'teaching'),
    'assessment': ('assess', 'marking'),
    'admin': ('admin', 'other admin'),
}
ORDER = ('module', 'person', 'contact', 'assessment', 'admin')


class ReadError(Exception):
    """The input couldn't be read at all"""


def read_cells(text=None, upload=None):
    """
    The non-empty rows from pasted text or an uploaded .csv/.xlsx file, as (row number, cells) with
    the cells as strings. Row numbers are as in the spreadsheet, counting blank rows.
    """
    if upload is not None:
        if upload.size > MAX_UPLOAD_BYTES:
            raise ReadError("That file is too large; the limit is 5 MB.")
        name = upload.name.lower()
        if name.endswith('.xlsx'):
            rows = _read_xlsx(upload)
        elif name.endswith('.csv') or name.endswith('.txt'):
            rows = _read_delimited(upload.read().decode('utf-8-sig', errors='replace'))
        else:
            raise ReadError("Please upload a .xlsx or .csv file, or paste the cells instead.")
    else:
        rows = _read_delimited(text or '')
    rows = [(number, [_text(cell) for cell in row]) for number, row in enumerate(rows, start=1)]
    rows = [(number, row) for number, row in rows if any(row)]
    if len(rows) > MAX_ROWS:
        raise ReadError(f"That's more than {MAX_ROWS} rows; please import it in parts.")
    return rows


def _text(cell):
    """A cell as text; whole numbers from Excel without a trailing .0"""
    if cell is None:
        return ''
    if isinstance(cell, float) and cell.is_integer():
        cell = int(cell)
    return str(cell).strip()


def _read_delimited(text):
    # Cells copied from a spreadsheet come tab separated; otherwise assume CSV
    delimiter = '\t' if '\t' in text else ','
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


def _read_xlsx(upload):
    try:
        import openpyxl
    except ImportError:
        raise ReadError("Excel files can't be read on this server; save it as CSV, or paste the cells instead.")
    try:
        workbook = openpyxl.load_workbook(upload, read_only=True, data_only=True)
    except Exception:
        raise ReadError("That doesn't look like an Excel (.xlsx) file.")
    sheet = workbook.worksheets[0]
    return [list(row) for row in sheet.iter_rows(values_only=True, max_row=MAX_ROWS + 50)]


def find_columns(rows):
    """
    Which column holds what, and whether the first row is a header. Without a recognisable header,
    the columns are taken in the usual order.
    """
    if rows:
        found = {}
        for index, cell in enumerate(rows[0][1]):
            label = cell.lower().strip()
            if label.startswith('module') and ('name' in label or 'title' in label):
                continue  # the module's name, not its code
            for key, starts in HEADERS.items():
                if key not in found and any(label.startswith(start) for start in starts):
                    found[key] = index
                    break
        if 'module' in found and 'person' in found and any(key in found for key, _ in CATEGORIES):
            return found, True
    return {key: index for index, key in enumerate(ORDER)}, False


def parse_hours(cell):
    """Hours from a cell: blank is 0; '7.5', '7.5h' and '7,5' are all 7.5. None if it isn't a number."""
    cleaned = re.sub(r'\s*(h|hrs?|hours?)$', '', cell.strip(), flags=re.IGNORECASE).replace(',', '.')
    if cleaned in ('', '-'):
        return Decimal(0)
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0:
        return None
    return value


def normalise(name):
    return re.sub(r'\s+', ' ', name.strip().lower())


class PeopleIndex:
    """Finds staff by name, username, email or staff number, among those who may be chosen"""

    TITLES = ('dr', 'prof', 'professor', 'mr', 'mrs', 'ms', 'miss', 'mx', 'sir', 'dame')

    def __init__(self, staff):
        self.keys = {}
        for person in staff:
            user = person.user
            first, last = normalise(user.first_name), normalise(user.last_name)
            initial = first[:1]
            for key in (user.username, user.email, person.staff_number, f"{first} {last}", f"{last}, {first}",
                        f"{last} {first}", f"{initial} {last}", f"{last}, {initial}"):
                key = normalise(key or '')
                if key and key != ',' and key.strip(', '):
                    self.keys.setdefault(key, set()).add(person)

    def find(self, text):
        """(staff, problem): the one person this text means, or why not"""
        key = normalise(text)
        if not key:
            return None, "No staff member given."
        matches = self.keys.get(key)
        if not matches:
            # Try without full stops ("A. Lee") and a title ("Dr. Ann Lee")
            words = re.sub(r'\.\s*', ' ', key).split()
            if words and words[0] in self.TITLES:
                words = words[1:]
            matches = self.keys.get(' '.join(words))
        if not matches:
            return None, f"No staff member in this work package matches \"{text}\"."
        if len(matches) > 1:
            return None, f"\"{text}\" matches more than one person; use their username or email instead."
        return next(iter(matches)), None


class Row:
    def __init__(self, line, module_text, person_text):
        self.line = line
        self.module_text = module_text
        self.person_text = person_text
        self.module = None
        self.staff = None
        self.hours = {}
        self.problems = []


class ModuleImport:
    """One module's rows, and the plan they make if they're all fine"""

    def __init__(self, module):
        self.module = module
        self.rows = []
        self.problems = []
        self.plan = None

    @property
    def ok(self):
        return self.plan is not None


class HoursImport:
    """
    Everything in a spreadsheet of hours per person: its rows, matched to modules and people in the
    package, with problems noted; and, for each module without problems, a plan.

    may_change  a function(module) saying whether the importer may change that module
    """

    def __init__(self, rows, package, staff_queryset, may_change):
        self.package = package
        self.rows = []
        self.unmatched = []  # rows whose module couldn't be found
        self.modules = []
        columns, self.has_header = find_columns(rows)
        if self.has_header:
            rows = rows[1:]

        people = PeopleIndex(staff_queryset)
        modules = {}
        for module in package.module_set.all():
            modules.setdefault(module.module_code.strip().upper(), []).append(module)
        by_module = {}

        def cell(row, key):
            index = columns.get(key)
            return row[index] if index is not None and index < len(row) else ''

        for number, cells in rows:
            row = Row(number, cell(cells, 'module'), cell(cells, 'person'))
            self.rows.append(row)
            for key, label in CATEGORIES:
                value = parse_hours(cell(cells, key))
                if value is None:
                    row.problems.append(f"{label} \"{cell(cells, key)}\" isn't a number of hours.")
                    value = Decimal(0)
                row.hours[key] = value
            row.staff, problem = people.find(row.person_text)
            if problem:
                row.problems.append(problem)

            matches = modules.get(row.module_text.strip().upper(), [])
            if len(matches) != 1:
                row.problems.append(
                    f"No module \"{row.module_text}\" in {package}." if not matches else
                    f"\"{row.module_text}\" matches more than one module in {package}; use the module's own "
                    f"page to enter its hours.")
                self.unmatched.append(row)
                continue
            row.module = matches[0]
            if row.module.pk not in by_module:
                by_module[row.module.pk] = ModuleImport(row.module)
                self.modules.append(by_module[row.module.pk])
            by_module[row.module.pk].rows.append(row)

        for item in self.modules:
            seen = set()
            for row in item.rows:
                if row.staff is not None and row.staff in seen:
                    row.problems.append(f"{row.staff} is listed more than once for {item.module.module_code}.")
                seen.add(row.staff)
            if not may_change(item.module):
                item.problems.append("You don't have permission to change this module's allocations.")
            if any(row.problems for row in item.rows):
                item.problems.append("Some of its rows have problems.")
            if not item.problems:
                plan = Plan(item.module, [(row.staff, row.hours) for row in item.rows])
                if not plan.people:
                    item.problems.append("No hours are given for anyone.")
                else:
                    item.plan = plan

    @property
    def ready(self):
        return [item for item in self.modules if item.ok]

    @property
    def skipped(self):
        return [item for item in self.modules if not item.ok]

    @property
    def problem_rows(self):
        return [row for row in self.rows if row.problems]

    def payload(self):
        """The ready modules' figures, as JSON, to carry from the preview to the confirmation"""
        return json.dumps([[item.module.pk, [[person['staff'].pk] + [str(c['entered']) for c in person['categories']]
                                             for person in item.plan.people]] for item in self.ready])

    def fingerprint(self):
        return fingerprint_plans([item.plan for item in self.ready])


def fingerprint_plans(plans):
    joined = '|'.join(plan.fingerprint() for plan in plans)
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def plans_from_payload(payload, package, staff_queryset, may_change):
    """
    Rebuild the plans from a preview's payload, checking everything again: each module must be in the
    package and changeable by the importer, and each person must be one who may be chosen.
    Returns the plans, or None if anything doesn't check out.
    """
    from .models import Module

    try:
        data = json.loads(payload)
    except (TypeError, ValueError):
        return None
    allowed = {person.pk: person for person in staff_queryset}
    plans = []
    try:
        for module_pk, people in data:
            module = Module.objects.filter(pk=int(module_pk), package=package).first()
            if module is None or not may_change(module):
                return None
            rows = []
            for staff_pk, *hours in people:
                staff = allowed.get(int(staff_pk))
                if staff is None or len(hours) != len(CATEGORIES):
                    return None
                values = [Decimal(value) for value in hours]
                if any(value < 0 for value in values):
                    return None
                rows.append((staff, {key: value for (key, _), value in zip(CATEGORIES, values)}))
            plans.append(Plan(module, rows))
    except (TypeError, ValueError, InvalidOperation):
        return None
    return plans
