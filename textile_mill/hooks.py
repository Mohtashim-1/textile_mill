app_name = "textile_mill"
app_title = "Textile Mill"
app_publisher = "Mission20 Zero"
app_description = "Integrated denim, home textile and knitting mill on ERPNext"
app_email = "shoaibmohtashim973@gmail.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "textile_mill",
		"logo": "/assets/textile_mill/images/textile-mill.svg",
		"title": "Textile Mill",
		"route": "/app/textile-mill-settings",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/textile_mill/css/textile_mill.css"
# app_include_js = "/assets/textile_mill/js/textile_mill.js"

# include js, css files in header of web template
# web_include_css = "/assets/textile_mill/css/textile_mill.css"
# web_include_js = "/assets/textile_mill/js/textile_mill.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "textile_mill/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Work Order": "public/js/work_order.js",
	"Batch": "public/js/batch.js",
	"Sales Order": "public/js/sales_order.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "textile_mill/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"textile_mill.print_utils.textile_qr",
		"textile_mill.print_utils.roll_lot",
		"textile_mill.print_utils.batch_qty",
		"textile_mill.print_utils.code128_svg",
		"textile_mill.print_utils.customer_label_spec",
	],
}
# jinja = {
# 	"methods": "textile_mill.utils.jinja_methods",
# 	"filters": "textile_mill.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "textile_mill.install.before_install"
after_install = "textile_mill.setup.install.after_install"
after_migrate = "textile_mill.setup.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "textile_mill.uninstall.before_uninstall"
# after_uninstall = "textile_mill.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "textile_mill.utils.before_app_install"
# after_app_install = "textile_mill.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "textile_mill.utils.before_app_uninstall"
# after_app_uninstall = "textile_mill.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "textile_mill.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Item": {
		"validate": "textile_mill.overrides.item.validate",
	},
	"Delivery Note": {
		"on_cancel": "textile_mill.overrides.delivery_note.release_packing_list",
		"on_trash": "textile_mill.overrides.delivery_note.release_packing_list",
	},
	"Stock Entry": {
		"before_validate": "textile_mill.overrides.stock_entry.before_validate",
	},
	"Work Order": {
		"before_validate": "textile_mill.overrides.work_order.before_validate",
		"validate": "textile_mill.overrides.work_order.validate",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"0 1 * * *": ["textile_mill.dashboards.snapshot.build_yesterday"],
	},
}

# Testing
# -------

# before_tests = "textile_mill.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "textile_mill.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "textile_mill.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["textile_mill.utils.before_request"]
# after_request = ["textile_mill.utils.after_request"]

# Job Events
# ----------
# before_job = ["textile_mill.utils.before_job"]
# after_job = ["textile_mill.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"textile_mill.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

