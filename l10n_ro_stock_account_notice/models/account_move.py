# Copyright (C) 2022 cbssolutions.ro
# Copyright (C) 2022 NextERP Romania
# Copyright (C) 2020 Terrabit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def l10n_ro_get_reception_account(self):
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
