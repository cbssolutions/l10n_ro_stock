# Copyright (C) 2014 Forest and Biomass Romania
# Copyright (C) 2020 NextERP Romania
# Copyright (C) 2020 Terrabit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class StockValuationLayer(models.Model):
    _name = "stock.valuation.layer"
    _inherit = ["stock.valuation.layer"]
    # we do not inherit , "l10n.ro.mixin" because is not woking with dpends= name and funciton is not working

    is_l10n_ro_record = fields.Boolean(
        string="Is Romanian Record",
        compute="_compute_is_l10n_ro_record",
        readonly=False,
    )
        
    @api.depends("value")
    def _compute_is_l10n_ro_record(self):
        for obj in self:
            has_company = "company_id" in self.env[obj._name]._fields
            has_company = has_company and obj.company_id
            company = obj.company_id if has_company else obj.env.company
            obj.is_l10n_ro_record = company._check_is_l10n_ro_record()


    l10n_ro_valued_type = fields.Char()

# alex 20220813 why the hell do we need them?
#  l10n_ro_invoice_id is used in a report, but l10n_ro_invoice_line_id nowhere
# and why not using account_move_id ?  

# we should use account_move_id   to be able to compare the validity of svl and 3xx acount
# also to see what hapends when we modify the account_move_id or set it to draft  (in another module) 
    l10n_ro_invoice_line_id = fields.Many2one(
        "account.move.line", string="Invoice Line"
    )
    l10n_ro_invoice_id = fields.Many2one("account.move", string="Invoice")

# and what is the need for l10n_ro_account_id?
# if you want l10n_ro_invoice_line_id    you can have related also the account
    l10n_ro_account_id = fields.Many2one(
        "account.account", compute="_compute_account", store=True
    )


############### alex ce dracu face compute account ???  adica mai jos???
    @api.depends("product_id", "account_move_id")
    def _compute_account(self):
        for svl in self.filtered(lambda sv: sv.stock_move_id.is_l10n_ro_record):
            account = self.env["account.account"]
            svl = svl.with_company(svl.stock_move_id.company_id)

            loc_dest = svl.stock_move_id.location_dest_id
            loc_scr = svl.stock_move_id.location_id
            account = (
                svl.product_id.l10n_ro_property_stock_valuation_account_id
                or svl.product_id.categ_id.property_stock_valuation_account_id
            )
            if svl.value > 0 and loc_dest.l10n_ro_property_stock_valuation_account_id:
                account = loc_dest.l10n_ro_property_stock_valuation_account_id
            if svl.value < 0 and loc_scr.l10n_ro_property_stock_valuation_account_id:
                account = loc_scr.l10n_ro_property_stock_valuation_account_id
            if svl.account_move_id:
                for aml in svl.account_move_id.line_ids.sorted(
                    lambda l: l.account_id.code
                ):
                    if aml.account_id.code[0] in ["2", "3"]:
                        if round(aml.balance, 2) == round(svl.value, 2):
                            account = aml.account_id
                            break
                        # if aml.balance <= 0 and svl.value <= 0:
                        #     account = aml.account_id
                        #     break
                        # if aml.balance > 0 and svl.value > 0:
                        #     account = aml.account_id
                        #     break
            if (
                svl.l10n_ro_valued_type in ("reception", "reception_return")
                and svl.l10n_ro_invoice_line_id
            ):
                account = svl.l10n_ro_invoice_line_id.account_id
            svl.l10n_ro_account_id = account

    # metoda dureaza foarte mult
    # def init(self):
    #     """ This method will compute values for valuation layer valued_type"""
    #     val_layers = self.search(
    #         ["|", ("valued_type", "=", False), ("valued_type", "=", "")]
    #     )
    #     val_types = self.env["stock.move"]._get_valued_types()
    #     val_types = [
    #         val
    #         for val in val_types
    #         if val not in ["in", "out", "dropshipped", "dropshipped_returned"]
    #     ]
    #     for layer in val_layers:
    #         if layer.stock_move_id:
    #             for valued_type in val_types:
    #                 if getattr(layer.stock_move_id, "_is_%s" % valued_type)():
    #                     layer.valued_type = valued_type
    #                     continue

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

#alex 20220813 not used
    # def _l10n_ro_compute_invoice_line_id(self):
        # for svl in self:
            # invoice_lines = self.env["account.move.line"]
            # stock_move = svl.stock_move_id
            # if not svl.l10n_ro_valued_type:
                # continue
            # if "reception" in svl.l10n_ro_valued_type:
                # invoice_lines = stock_move.purchase_line_id.invoice_lines
            # if "delivery" in svl.l10n_ro_valued_type:
                # invoice_lines = stock_move.sale_line_id.invoice_lines
                #
            # if len(invoice_lines) == 1:
                # svl.l10n_ro_invoice_line_id = invoice_lines
                # svl.l10n_ro_invoice_id = invoice_lines.move_id
            # else:
                # for line in invoice_lines:
                    # if stock_move.date.date() == line.move_id.date:
                        # svl.l10n_ro_invoice_line_id = line
                        # svl.l10n_ro_invoice_id = line.move_id
