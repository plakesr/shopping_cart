# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import get_fullname, flt
from shopping_cart.shopping_cart.doctype.shopping_cart_settings.shopping_cart_settings import is_shopping_cart_enabled, get_default_territory

# TODO
# validate stock of each item in Website Warehouse or have a list of possible warehouses in Shopping Cart Settings

def get_quotation(user=None):
	if not user:
		user = frappe.session.user
	if user == "Guest":
		raise frappe.PermissionError

	is_shopping_cart_enabled()
	party = get_party(user)
	values = {
		"order_type": "Shopping Cart",
		party.doctype.lower(): party.name,
		"docstatus": 0,
		"contact_email": user
	}

	try:
		quotation = frappe.get_doc("Quotation", values)
	except frappe.DoesNotExistError:
		quotation = frappe.new_doc("Quotation")
		quotation.update(values)
		if party.doctype == "Customer":
			quotation.contact_person = frappe.db.get_value("Contact", {"customer": party.name, "email_id": user})
		quotation.insert(ignore_permissions=True)

	return quotation

def set_item_in_cart(item_code, qty, user=None):
	validate_item(item_code)
	quotation = get_quotation(user=user)
	qty = flt(qty)
	quotation_item = quotation.get("quotation_details", {"item_code": item_code})

	if qty==0:
		if quotation_item:
			# remove
			quotation.get("quotation_details").remove(quotation_item[0])
	else:
		# add or update
		if quotation_item:
			quotation_item[0].qty = qty
		else:
			quotation.append("quotation_details", {
				"doctype": "Quotation Item",
				"item_code": item_code,
				"qty": qty
			})

	quotation.save(ignore_permissions=True)
	return quotation

def set_address_in_cart(address_fieldname, address, user=None):
	quotation = get_quotation(user=user)
	validate_address(quotation, address_fieldname, address)

	if quotation.get(address_fieldname) != address:
		quotation.set(address_fieldname, address)
		if address_fieldname=="customer_address":
			quotation.set("address_display", None)
		else:
			quotation.set("shipping_address", None)

		quotation.save(ignore_permissions=True)

	return quotation

def validate_item(item_code):
	item = frappe.db.get_value("Item", item_code, ["item_name", "show_in_website"], as_dict=True)
	if not item.show_in_website:
		frappe.throw(_("{0} cannot be purchased using Shopping Cart").format(item.item_name))

def validate_address(quotation, address_fieldname, address):
	party = get_party(quotation.contact_email)
	address_doc = frappe.get_doc(address)
	if address_doc.get(party.doctype.lower()) != party.name:
		if address_fieldname=="customer_address":
			frappe.throw(_("Invalid Billing Address"))
		else:
			frappe.throw(_("Invalid Shipping Address"))

def get_party(user):
	def _get_party(user):
		customer = frappe.db.get_value("Contact", {"email_id": user}, "customer")
		if customer:
			return frappe.get_doc("Customer", customer)

		lead = frappe.db.get_value("Lead", {"email_id": user})
		if lead:
			return frappe.get_doc("Lead", lead)

		# create a lead
		lead = frappe.new_doc("Lead")
		lead.update({
			"email_id": user,
			"lead_name": get_fullname(user),
			"territory": guess_territory()
		})
		lead.insert(ignore_permissions=True)

		return lead

	if not getattr(frappe.local, "shopping_cart_party", None):
		frappe.local.shopping_cart_party = {}

	if not frappe.local.shopping_cart_party.get(user):
		frappe.local.shopping_cart_party[user] = _get_party(user)

	return frappe.local.shopping_cart_party[user]

def guess_territory():
	territory = None
	if frappe.session.get("session_country"):
		territory = frappe.db.get_value("Territory", frappe.session.get("session_country"))

	return territory or get_default_territory()
