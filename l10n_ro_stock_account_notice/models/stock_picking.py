# Copyright (C) 2022 cbssolutions.ro
# Copyright (C) 2014 Forest and Biomass Romania
# Copyright (C) 2020 NextERP Romania
# Copyright (C) 2020 Terrabit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "l10n.ro.mixin"]

    # Prin acest camp se indica daca un produs care e stocabil trece prin
    # contul 408 / 418 la achizitie sau vanzare
    # receptie/ livrare in baza de aviz
    l10n_ro_notice = fields.Boolean(
        "Is a notice",
        states={"done": [("readonly", True)], "cancel": [("readonly", True)]},
        default=False,
        help="With this field the reception/delivery is set as a notice. "
        "The generated account move will contain accounts 408/418.",
    )
    l10n_ro_accounting_date = fields.Datetime(
        "Accounting Date",
        copy=False,
        help="If this field is set, the svl and accounting entiries will "
        "have this date for notice, If not will have the today date as it should be",
        tracking=True,
    )
    
    @api.constrains("picking_type_id", "l10n_ro_notice")
    def _check_recursion(self):
        for rec in self:
            if rec.l10n_ro_notice and rec.picking_type_id.code not in ["incoming", "outgoing"]:
                raise ValidationError(_(f'For picking=({rec.id},{rec.name}) you have l10n_ro_notice but picking_type_code={rec.picking_type_code} that is not in ["incoming", "outgoing"]'))
