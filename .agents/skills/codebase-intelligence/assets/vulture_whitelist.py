# Names that vulture will report as unused but which are actually called
# dynamically (decorators, signal handlers, plugin entry points, etc.).
#
# Add `_.<name>` for each false positive vulture reports on first run.
# Pass this file to vulture explicitly:
#     vulture src/ .vulture-whitelist.py --min-confidence 80

# Examples — replace with your actual dynamic callables.
_.handle_signup_complete
_.handle_payment_received
_.export_as_csv
_.validate_email_domain
