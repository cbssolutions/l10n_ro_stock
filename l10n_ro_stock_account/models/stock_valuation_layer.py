# Copyright (C) 2014 Forest and Biomass Romania
# Copyright (C) 2022 NextERP Romania
# Copyright (C) 2020 Terrabit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class StockValuationLayer(models.Model):
    _inherit = "stock.valuation.layer"

    l10n_ro_valued_type = fields.Char()  # just a name we can live also without
    l10n_ro_bill_accounting_date = fields.Date(
        readonly=True,
        help="This is the date from billing accounting date. The bill that generate this svl",
    )
    # fields to work the set to draft and post again to change the values/ date
    l10n_ro_draft_svl_id = fields.Many2one("stock.valuation.layer", readonly=0, help="was created from a setting to draft. is the reverse of this svl")
    l10n_ro_draft_svl_ids = fields.One2many("stock.valuation.layer","l10n_ro_draft_svl_id", readonly=0, help="it's value was nulled (at setting to draft the account_move) by this entry")
    l10n_ro_location_dest_id = fields.Many2one("stock.location", readonly=0, 
                                            store=1,
                                            related="stock_move_id.location_dest_id",
                                           help="Destination Location value taken from move to be able to aproximate the value of stock in a location")
    
    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if self.env["res.company"]._check_is_l10n_ro_record(
                values.get("company_id")
            ):
                if (
                    "l10n_ro_valued_type" not in values
                    and "stock_valuation_layer_id" in values
                ):
                    svl = self.env["stock.valuation.layer"].browse(
                        values["stock_valuation_layer_id"]
                    )
                    if svl:
                        values["l10n_ro_valued_type"] = svl.l10n_ro_valued_type
        return super(StockValuationLayer, self).create(vals_list)
