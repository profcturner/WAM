"""
Django settings for WAM project.

https://github.com/profcturner/WAM/

This settings file may change in updates, in general you should copy aspects you need to override into
a local_settings.py file in the same directory.

"""


import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret! And don't use this.
SECRET_KEY = 'i(@t%n%skz1v)y-%b4+krov&l1efdc__m+oh!jn59%(!4n1r7+'

# Here are some important system wide settings for Django. Override in local_settings.py
WAM_VERSION = "3.0.0.beta"
WAM_URL = "http://localhost"
WAM_AUTO_EMAIL_FROM = "noreply@invalid.com"
WAM_ADMIN_CONTACT_EMAIL = "noreply@invalid.com"
WAM_ADMIN_CONTACT_NAME = "Help Desk"

# These regexs will be used for automatic creation of Staff objects when an authenticated User is created
# They can be used to help WAM establish whether this should be a member of Academic Staff and External Examiner
# If these regexs are set, and an authenticated User is presented, login will be disabled
WAM_STAFF_REGEX = None
WAM_EXTERNAL_REGEX = None

# This is the activity type for module staff allocations, you may need to change this if you ran WAM before 3.0.0
WAM_DEFAULT_ACTIVITY_TYPE = 1

# Whether to have ADFS authentication
# You will need other configuration changes, please see
# https://github.com/profcturner/WAM/wiki/ADFS---Azure-Authentication
WAM_ADFS_AUTH = False

# The following settings are usually used with some form of external authentication as above
# And if enabled, will create Campuses, Faculties and Schools for authenticated users belonging to unknown ones.
# This allows WAM to automatically learn your University structure
WAM_AUTO_CREATE_CAMPUS = True
WAM_AUTO_CREATE_FACULTY = True
WAM_AUTO_CREATE_SCHOOL = True

# Automatically create School level "Groups"
WAM_AUTO_CREATE_SCHOOL_GROUPS = True

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
DEBUG_TOOLBAR = False
#ALLOWED_HOSTS = ["127.0.0.1"]
ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admindocs',
    'django.contrib.humanize',
    'fancy_formset',
    'loads'
)

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.admindocs.middleware.XViewMiddleware',
)

ROOT_URLCONF = 'WAM.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'loads.context_processors.staff',
                'loads.context_processors.auth_adfs',
            ],
        },
    },
]

WSGI_APPLICATION = 'WAM.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

STATIC_URL = '/static/'

# Where do we store media
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = 'logged out'

# New in Django 3.2, we should set an explicit automatic primary key type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

from django.contrib.messages import constants as messages

# This maps Bootstrap styles to Django messages
MESSAGE_TAGS = {
        messages.DEBUG: 'alert-secondary',
        messages.INFO: 'alert-info',
        messages.SUCCESS: 'alert-success',
        messages.WARNING: 'alert-warning',
        messages.ERROR: 'alert-danger',
}

# Create a local settings file called local_settings.py to override details
try:
    from WAM.local_settings import *
except ImportError:
    pass