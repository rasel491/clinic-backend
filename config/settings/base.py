from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = 'change-me'

DEBUG = False

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'corsheaders',
#    ' rest_framework_simplejwt',

    # Local apps
    'apps.accounts.apps.AccountsConfig',
    'apps.audit.apps.AuditConfig',
    'apps.billing.apps.BillingConfig',
    'apps.clinics.apps.ClinicsConfig',
    'apps.doctors.apps.DoctorsConfig',
    'apps.eod.apps.EodConfig',
    'apps.integrations.apps.IntegrationsConfig',
    'apps.notifications.apps.NotificationsConfig',
    'apps.otp.apps.OtpConfig',
    'apps.patients.apps.PatientsConfig',
    'apps.payments.apps.PaymentsConfig',
    'apps.prescriptions.apps.PrescriptionsConfig',
    'apps.reports.apps.ReportsConfig',
    'apps.settings_core.apps.SettingsCoreConfig',
    'apps.treatments.apps.TreatmentsConfig',
    'apps.visits.apps.VisitsConfig',
    
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
