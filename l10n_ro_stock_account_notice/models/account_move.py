# Copyright (C) 2022 cbssolutions.ro
# Copyright (C) 2022 NextERP Romania
# Copyright (C) 2020 Terrabit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
from odoo import _, api, models, fields

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # we created 2 fields to be more clear in fields and at selection without so much code
    l10n_ro_invoice_for_pickings_ids = fields.One2many(
        "stock.picking","l10n_ro_notice_invoice_id",
        help="If this field is set,means that this is the invoice "
        "for set notice pickings. A notice picking can be invoiced only on one invoice!",
        string = "For notice delivery pickings",
        readonly=0,
        copy=0,
        tracking=1,
    )

    l10n_ro_bill_for_pickings_ids = fields.One2many(
        "stock.picking","l10n_ro_notice_bill_id",
        string = "For notice reception pickings",
        help="If this field is set,means that this is the bill "
        "for set notice pickings. A notice picking can be billed only on one bill!",
        readonly=0,
        copy=0,
        tracking=1,
    )

    @api.onchange("l10n_ro_bill_for_pickings_ids", "l10n_ro_invoice_for_pickings_ids")
    def _onchange_l10n_ro_for_pickings(self):
        if self.invoice_line_ids and (self.l10n_ro_bill_for_pickings_ids or self.l10n_ro_invoice_for_pickings_ids):
           return {
                'warning': {'title': _('Warning'), 'message': _('By having bill/invoice_for_pickings_ids is expected that products to have 408 418 accounts. If is the case change manualy the accounts at products ( or enter again the invoice_lines). '),},
               }
             
    
    def _get_reception_account(self):
        self.ensure_one()
        account = self.env["account.account"]
        if not self.is_l10n_ro_record:
            return account

        acc_payable = self.company_id.l10n_ro_property_stock_picking_payable_account_id
        valuation_stock_moves = self.env["stock.move"].search(
            [
                (
                    "purchase_line_id",
                    "in",
                    self.line_ids.mapped("purchase_line_id").ids,
                ),
                ("state", "=", "done"),
                ("picking_id.notice", "=", True),
                ("product_qty", "!=", 0.0),
            ]
        )
        if valuation_stock_moves:
            acc_moves = valuation_stock_moves.mapped("account_move_ids")
            lines = self.env["account.move.line"].search(
                [("move_id", "in", acc_moves.ids)]
            )
            lines_diff_acc = lines.mapped("account_id").filtered(
                lambda a: a != acc_payable
            )
            if lines_diff_acc:
                account = lines_diff_acc[0]
        return account

    def _stock_account_prepare_anglo_saxon_in_lines_vals(self):
        if self.is_l10n_ro_record:
            return []
        return super()._stock_account_prepare_anglo_saxon_in_lines_vals()
