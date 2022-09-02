# Copyright (C) 2022 cbssolutions.ro
from odoo import models

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _prepare_invoice(self):
        # from invoiced products we are getting coresponding the notice picking
        # to set in invoice as l10n_ro_bill_for_pickings_ids
        invoice_vals = super()._prepare_invoice()
        inv_for_reception_picking = self._context.get("inv_for_reception_picking")
        if l10n_ro_bill_for_pickings_ids:
            invoice_vals["l10n_ro_bill_for_pickings_ids"] = [(6,0,l10n_ro_bill_for_pickings_ids.ids)]
        return invoice_vals
