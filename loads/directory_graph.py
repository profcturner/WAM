"""
A DirectorySource that reads staff from Microsoft Entra ID (Azure AD) using
the Microsoft Graph API.

To use it, register an application in Entra ID with the Microsoft Graph
*application* permission User.Read.All (granted admin consent), and set:

    WAM_DIRECTORY_SOURCE = "loads.directory_graph.GraphDirectorySource"
    WAM_GRAPH_TENANT_ID = "..."
    WAM_GRAPH_CLIENT_ID = "..."
    WAM_GRAPH_CLIENT_SECRET = "..."     # ideally read from the environment

The defaults below suit many tenants, but can be changed in local_settings.py:

    WAM_GRAPH_SCHOOL_ATTRIBUTE      the Graph user property holding the School
                                    (default "department")
    WAM_GRAPH_FILTER                extra OData $filter clause, ANDed with the
                                    School match, e.g. "employeeType eq 'Staff'"
    WAM_GRAPH_ATTRIBUTE_MAP         staff record field -> Graph user property.
                                    Dotted paths reach nested properties, e.g.
                                    "onPremisesExtensionAttributes.extensionAttribute1"

Make sure the "username" mapping produces the same value as the claim your
authentication backend uses as the username, or staff will get a second
account at first login.

Where an institution needs more than an attribute map (for example, working out
who is an External Examiner), subclass GraphDirectorySource and override
to_record(). Return None from it to skip a user.
"""
import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from loads.directory import DirectorySource

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.microsoft.com/v1.0"

DEFAULT_ATTRIBUTE_MAP = {
    'username': 'userPrincipalName',
    'first_name': 'givenName',
    'last_name': 'surname',
    'email': 'mail',
    'job_title': 'jobTitle',
    'school': 'department',
    'faculty': 'companyName',
    'campus': 'officeLocation',
}


def get_path(obj, path):
    """Fetch a value from nested dicts using a dotted path, or None."""
    for part in path.split('.'):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


def odata_string(value):
    """Quote a value as an OData string literal."""
    return "'" + str(value).replace("'", "''") + "'"


class GraphDirectorySource(DirectorySource):
    """Reads staff records from Microsoft Graph."""

    # Further Graph properties to $select, beyond those in the attribute map,
    # for subclasses whose to_record() needs them
    extra_select = ()

    def __init__(self):
        self.attribute_map = getattr(settings, 'WAM_GRAPH_ATTRIBUTE_MAP', None) or DEFAULT_ATTRIBUTE_MAP
        self.school_attribute = getattr(settings, 'WAM_GRAPH_SCHOOL_ATTRIBUTE', 'department')
        self.extra_filter = getattr(settings, 'WAM_GRAPH_FILTER', '')
        self._token = None

    # Authentication

    def get_token(self):
        """Get an app-only access token for Graph using client credentials."""
        try:
            import msal
        except ImportError:
            raise ImproperlyConfigured("GraphDirectorySource needs the msal package: pip install msal")

        for name in ('WAM_GRAPH_TENANT_ID', 'WAM_GRAPH_CLIENT_ID', 'WAM_GRAPH_CLIENT_SECRET'):
            if not getattr(settings, name, None):
                raise ImproperlyConfigured(f"{name} is not set")

        app = msal.ConfidentialClientApplication(
            client_id=settings.WAM_GRAPH_CLIENT_ID,
            client_credential=settings.WAM_GRAPH_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{settings.WAM_GRAPH_TENANT_ID}",
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if 'access_token' not in result:
            raise ImproperlyConfigured(
                f"could not get a Graph token: {result.get('error_description', result.get('error'))}")
        return result['access_token']

    @property
    def token(self):
        if self._token is None:
            self._token = self.get_token()
        return self._token

    # Querying

    def select_attributes(self):
        """The top level Graph properties to request."""
        paths = list(self.attribute_map.values()) + list(self.extra_select)
        return sorted({path.split('.')[0] for path in paths})

    def build_filter(self, school):
        clauses = [f"{self.school_attribute} eq {odata_string(school)}", "accountEnabled eq true"]
        if self.extra_filter:
            clauses.append(f"({self.extra_filter})")
        return ' and '.join(clauses)

    def graph_users(self, school):
        """Yield raw Graph user objects in the School, following paging links."""
        import requests

        url = f"{GRAPH_URL}/users"
        params = {
            '$filter': self.build_filter(school),
            '$select': ','.join(self.select_attributes()),
            '$count': 'true',
            '$top': '999',
        }
        # ConsistencyLevel and $count enable Graph's "advanced queries", which
        # filters on some properties (e.g. extension attributes) require
        headers = {'Authorization': f"Bearer {self.token}", 'ConsistencyLevel': 'eventual'}

        while url:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            if response.status_code == 403:
                raise ImproperlyConfigured(
                    "Graph refused the query (403): has User.Read.All application permission "
                    "been granted admin consent?")
            response.raise_for_status()
            data = response.json()
            yield from data.get('value', [])
            # The next link already carries the query parameters
            url, params = data.get('@odata.nextLink'), None

    def to_record(self, graph_user):
        """
        Turn a Graph user object into a staff record, or None to skip the user.

        Override this for institution specific rules.
        """
        return {field: get_path(graph_user, path) for field, path in self.attribute_map.items()}

    def staff_in_school(self, school):
        for graph_user in self.graph_users(school):
            record = self.to_record(graph_user)
            if record is None:
                logger.debug("skipping graph user %s", graph_user.get('userPrincipalName'))
                continue
            yield record
