# Copyright (C) 2022 cbssolutions.ro
# Copyright (C) 2014 Forest and Biomass Romania
# Copyright (C) 2020 NextERP Romania
# Copyright (C) 2020 Terrabit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import api, models
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _name = "stock.move"
    _inherit = ["stock.move", "l10n.ro.mixin"]

    @api.model
    def _get_valued_types(self):
        valued_types = super(StockMove, self)._get_valued_types()
        if self.filtered("is_l10n_ro_record"):
            valued_types.remove("out")  # we have delivery, and we do need aditional svl
            valued_types += [
                "reception",  # receptie de la furnizor fara aviz
                "reception_return",  # retur la o receptie de la funizor fara aviz
                "delivery",  # livrare din stoc fara aviz
                "delivery_return",  # storno livrare
                "plus_inventory",
                "minus_inventory",
                "consumption",  # consum in productie
                "consumption_return",  # storno consum produse
                "production",  # inregistrare produse finite/semifabricate prin productie
                "production_return",  # storno productie
                "internal_transfer",  # transfer intern
                "usage_giving",
                "usage_giving_return",
            ]
        return valued_types

    # nu se mai face in mod automat evaluarea la intrare in stoc
    def _create_in_svl(self, forced_quantity=None):
        _logger.debug("SVL:%s" % self.env.context.get("valued_type", ""))
        if self.env.context.get("standard") or not self.filtered("is_l10n_ro_record"):
            svl = super(StockMove, self)._create_in_svl(forced_quantity)
        else:
            svl = self.env["stock.valuation.layer"]
        return svl

    def _is_returned(self, valued_type):
        """Este tot timpul False deoarece noi tratam fiecare caz in parte
        de retur si fxam conturile"""
        if not self.is_l10n_ro_record:
            return super()._is_returned(valued_type)
        return False

    # evaluare la receptie
    def _is_reception(self):
        "Este receptie in stoc fara aviz. We are making the svl at invoice"
        return (
            self.is_l10n_ro_record
            and self.location_id.usage == "supplier"
            and self._is_in()
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )

    def _create_reception_svl(self, forced_quantity=None):
        # till the bill form supplier the value of stock is 0
        svl_vals_list = []
        for move in self:
            picking = move.picking_id
            svl_vals_list.append(
                {
                    "description": f"Reception picking=({picking.name},{picking.id})",
                    "account_move_id": False,
                    "stock_move_id": move.id,
                    "product_id": move.product_id.id,
                    "company_id": move.company_id.id,
                    "value": 0,
                    "remaining_value": 0,
                    "l10n_ro_bill_accounting_date": False, # will be put at invoice
                    "quantity": move.quantity_done,
                    "remaining_qty": move.quantity_done,
                    "unit_cost": 0,
                    "l10n_ro_valued_type": "reception",
                })
        return self.env["stock.valuation.layer"].create(svl_vals_list)

    def _is_reception_return(self):
        """Este un retur la o receptie in stoc fara aviz"""
        it_is = (
            self.is_l10n_ro_record
            and self.location_dest_id.usage == "supplier"
            and self._is_out()
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )
        return it_is

    def _create_reception_return_svl(self, forced_quantity=None):
        created_svl = self.env["stock.valuation.layer"]
        for move in self:
            # self are created stock_moves to return to supplier
            move = move.with_context(standard=True, valued_type="reception_return")
            if (
                move.origin_returned_move_id
                and move.origin_returned_move_id.sudo().stock_valuation_layer_ids
            ):
                move = move.with_context(
                    origin_return_candidates=move.origin_returned_move_id.sudo()
                    .stock_valuation_layer_ids.filtered(lambda sv: sv.remaining_qty > 0)
                    .ids
                )
                svl =  move._create_out_svl(forced_quantity)
                if not svl:
                    continue

                journal_id, acc_src, acc_dest, acc_valuation = move._get_accounting_data_for_valuation()

                
                picking = move.picking_id
                product = move.product_id
                accounts = product._get_product_accounts()
                # we need to create the reception_return account_entries with the value from svl
                # if not we will have diffrence in 3xx acount
                created_account_move = self.sudo().env['account.move'].create({
                    "move_type": "entry",
                    "date":move.date,
                    "journal_id":journal_id,
                    "company_id":move.company_id.id,
                    "ref": f"reception_return_picking={picking.name}",
                    "line_ids":[(0,0,{
                        "product_id": product.id,
                        "debit":abs(svl.value),
                        "credit":0,
                        "quantity":move.quantity_done,
                        "account_id":accounts["expense"].id,
                        "name":f"reception_return_picking product={product.name}, qty={move.quantity_done}, unit_price={svl.unit_cost}"
                        }),
                                (0,0,{
                        "product_id": product.id,
                        "debit":0,
                        "credit":abs(svl.value),
                        "quantity":move.quantity_done,
                        "account_id":acc_dest,
                        "name":f"reception_return_picking product={product.name}, qty={move.quantity_done}, unit_price={svl.unit_cost}"
                                    })],
                    
                })
                created_account_move.action_post()
                svl.account_move_id = created_account_move
            created_svl += svl
        return created_svl

    def _is_delivery(self):
        """Este livrare din stoc fara aviz"""
        return (
            self.is_l10n_ro_record
            and self.location_dest_id.usage == "customer"
            and self._is_out()
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )

    def _create_delivery_svl(self, forced_quantity=None):
        move = self.with_context(standard=True, valued_type="delivery")
        return move._create_out_svl(forced_quantity)

    def _is_delivery_return(self):
        """Este retur la o livrare din stoc fara aviz"""
        it_is = (
            self.is_l10n_ro_record
            and self.location_id.usage == "customer"
            and self._is_in()
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )
        return it_is

    def _create_delivery_return_svl(self, forced_quantity=None):
        move = self.with_context(standard=True, valued_type="delivery_return")
        return move._create_in_svl(forced_quantity)

    def _is_plus_inventory(self):
        it_is = (
            self.is_l10n_ro_record
            and self.location_id.usage == "inventory"
            and self.location_dest_id.usage == "internal"
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )
        return it_is

    def _create_plus_inventory_svl(self, forced_quantity=None):

        move = self.with_context(standard=True, valued_type="plus_inventory")
        return move._create_in_svl(forced_quantity)

    def _is_minus_inventory(self):
        it_is = (
            self.is_l10n_ro_record
            and self.location_id.usage == "internal"
            and self.location_dest_id.usage == "inventory"
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )
        return it_is

    def _create_minus_inventory_svl(self, forced_quantity=None):
        move = self.with_context(standard=True, valued_type="minus_inventory")
        return move._create_out_svl(forced_quantity)

    def _is_production(self):
        """Este inregistrare intrare produse finite prin productie"""
        it_is = (
            self.is_l10n_ro_record
            and self._is_in()
            and self.location_id.usage == "production"
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )
        return it_is

    def _create_production_svl(self, forced_quantity=None):
        move = self.with_context(standard=True, valued_type="production")
        return move._create_in_svl(forced_quantity)

    def _is_production_return(self):
        """Este retur inregistrare produse finite prin productie"""
        it_is = (
            self.company_id.l10n_ro_accounting
            and self._is_out()
            and self.location_dest_id.usage == "production"
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )
        return it_is

    def _create_production_return_svl(self, forced_quantity=None):
        move = self.with_context(standard=True, valued_type="production_return")
        return move._create_out_svl(forced_quantity)

    def _is_consumption(self):
        """Este un conusm de materiale in productie"""
        it_is = (
            self.is_l10n_ro_record
            and self._is_out()
            and self.location_dest_id.usage == "consume"
            and not self.origin_returned_move_id
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )
        return it_is

    def _create_consumption_svl(self, forced_quantity=None):
        move = self.with_context(standard=True, valued_type="consumption")
        return move._create_out_svl(forced_quantity)

    def _is_consumption_return(self):
        """Este un conusm de materiale in productie"""
        it_is = (
            self.is_l10n_ro_record
            and self._is_in()
            and self.location_id.usage == "consume"
            and self.origin_returned_move_id
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )
        return it_is

    def _create_consumption_return_svl(self, forced_quantity=None):
        move = self.with_context(standard=True, valued_type="consumption_return")
        return move._create_in_svl(forced_quantity)

    def _is_internal_transfer(self):
        """Este transfer intern"""
        it_is = (
            self.is_l10n_ro_record
            and self.location_dest_id.usage == "internal"
            and self.location_id.usage == "internal"
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )
        return it_is

    # cred ca este mai bine sa generam doua svl - o intrare si o iesire
    # alex 202208 not verified
    def _create_internal_transfer_svl(self, forced_quantity=None):
        svl_vals_list = []
        for move in self.with_context(standard=True, valued_type="internal_transfer"):
            move = move.with_company(move.company_id.id)

            valued_move_lines = move.move_line_ids
            valued_quantity = 0
            for valued_move_line in valued_move_lines:
                valued_quantity += valued_move_line.product_uom_id._compute_quantity(
                    valued_move_line.qty_done, move.product_id.uom_id
                )
            if float_is_zero(
                forced_quantity or valued_quantity,
                precision_rounding=move.product_id.uom_id.rounding,
            ):
                continue
            svl_vals = move.product_id._prepare_out_svl_vals(
                forced_quantity or valued_quantity, move.company_id
            )
            svl_vals.update(move._prepare_common_svl_vals())
            if forced_quantity:
                svl_vals["description"] = (
                    "Correction of %s (modification of past move)"
                    % move.picking_id.name
                    or move.name
                )
            svl_vals["description"] += svl_vals.pop("rounding_adjustment", "")
            svl_vals_list.append(svl_vals)

            new_svl_vals = svl_vals.copy()
            new_svl_vals.update(
                {
                    "quantity": abs(svl_vals.get("quantity", 0)),
                    "remaining_qty": abs(svl_vals.get("quantity", 0)),
                    "unit_cost": abs(svl_vals.get("unit_cost", 0)),
                    "value": abs(svl_vals.get("value", 0)),
                    "remaining_value": abs(svl_vals.get("value", 0)),
                }
            )
            svl_vals_list.append(new_svl_vals)

        return self.env["stock.valuation.layer"].sudo().create(svl_vals_list)

    def _is_usage_giving(self):
        """Este dare in folosinta"""
        it_is = (
            self.is_l10n_ro_record
            and self.location_dest_id.usage == "usage_giving"
            and self._is_out()
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )

        return it_is

    def _create_usage_giving_svl(self, forced_quantity=None):
        move = self.with_context(standard=True, valued_type="usage_giving")
        return move._create_out_svl(forced_quantity)

    def _is_usage_giving_return(self):
        """Este return dare in folosinta"""
        it_is = (
            self.is_l10n_ro_record
            and self.location_id.usage == "usage_giving"
            and self._is_in()
            and self.product_id.type == "product"
            and self.product_id.valuation == "real_time"
        )
        return it_is

    def _create_usage_giving_return_svl(self, forced_quantity=None):
        move = self.with_context(standard=True, valued_type="usage_giving_return")
        return move._create_in_svl(forced_quantity)

    def _prepare_common_svl_vals(self):
        vals = super(StockMove, self)._prepare_common_svl_vals()
        if self.is_l10n_ro_record:
            valued_type = self.env.context.get("valued_type")
            if valued_type:
                vals["l10n_ro_valued_type"] = valued_type
            # vals[
            # "l10n_ro_account_id"
            # ] = self.product_id.categ_id.property_stock_valuation_account_id.id
        return vals

    def _create_dropshipped_svl(self, forced_quantity=None):
        valued_type = "dropshipped"
        self = self.with_context(valued_type=valued_type)
        return super(StockMove, self)._create_dropshipped_svl(forced_quantity)

    def _get_company(self, svl):
        self.ensure_one()
        company_from = (
            self._is_out()
            and self.mapped("move_line_ids.location_id.company_id")
            or False
        )
        company_to = (
            self._is_in()
            and self.mapped("move_line_ids.location_dest_id.company_id")
            or False
        )

        if self._is_in():
            return company_to

        if self._is_out():
            return company_from

        return self.env.company

    def _account_entry_move(self, qty, description, svl_id, cost):
        """Accounting Valuation Entries"""
        if self.is_l10n_ro_record:
            svl = self.env["stock.valuation.layer"].browse(svl_id)
            company = self._get_company(svl)
            self = company and self.with_company(company.id) or self
            if company and company.l10n_ro_accounting:
                self = self.with_context(
                    valued_type=svl.l10n_ro_valued_type, is_l10n_ro_accounting=True
                )

        res = super(StockMove, self)._account_entry_move(qty, description, svl_id, cost)

        if self.is_l10n_ro_record:
            self._romanian_account_entry_move(qty, description, svl_id, cost)

        return res

    def _romanian_account_entry_move(self, qty, description, svl_id, cost):
        location_from = self.location_id
        location_to = self.location_dest_id
        svl = self.env["stock.valuation.layer"]

        if self._is_usage_giving() or self._is_usage_giving_return():
            # inregistrare dare in folosinta 8035
            move = self.with_context(valued_type="usage_giving_secondary")
            (
                journal_id,
                acc_src,
                acc_dest,
                acc_valuation,
            ) = move._get_accounting_data_for_valuation()
            move._create_account_move_line(
                acc_src, acc_dest, journal_id, qty, description, svl, cost
            )

        if self._is_internal_transfer():
            move = self.with_context(valued_type="internal_transfer")
            (
                journal_id,
                acc_src,
                acc_dest,
                acc_valuation,
            ) = move._get_accounting_data_for_valuation()
            if location_to.l10n_ro_property_stock_valuation_account_id and cost < 0:
                move._create_account_move_line(
                    acc_dest, acc_valuation, journal_id, qty, description, svl_id, cost
                )
            if location_from.l10n_ro_property_stock_valuation_account_id and cost > 0:
                move._create_account_move_line(
                    acc_src, acc_valuation, journal_id, qty, description, svl_id, cost
                )

    def _create_account_move_line(
        self,
        credit_account_id,
        debit_account_id,
        journal_id,
        qty,
        description,
        svl_id,
        cost,
    ):
        # nu mai trebuie generate notele contabile de la cont de stoc la cont de stoc
        # valabil doar pentru dare in folosinta
        if (
            self.is_l10n_ro_record
            and credit_account_id == debit_account_id
            and not self._is_usage_giving()
            and not self._is_usage_giving_return()
        ):
            return
        return super(StockMove, self)._create_account_move_line(
            credit_account_id,
            debit_account_id,
            journal_id,
            qty,
            description,
            svl_id,
            cost,
        )

    def _get_accounting_data_for_valuation(self):
        """retunns different values if self.is_l10n_ro_record & self.product_id.categ_id.l10n_ro_stock_account_change
        not used 202208 alex
        """
        journal_id, acc_src, acc_dest, acc_valuation = super(
            StockMove, self
        )._get_accounting_data_for_valuation()
        if (
            self.is_l10n_ro_record
            and self.product_id.categ_id.l10n_ro_stock_account_change
        ):
            location_from = self.location_id
            location_to = self.location_dest_id
            valued_type = self.env.context.get("valued_type", "indefinite")
            # produsele din aceasta locatia folosesc pentru evaluare contul
            if location_to.l10n_ro_property_stock_valuation_account_id:
                # in cazul unui transfer intern se va face contare dintre
                # contul de stoc si contul din locatie
                if valued_type == "internal_transfer":
                    acc_dest = (
                        location_to.l10n_ro_property_stock_valuation_account_id.id
                    )
                else:
                    acc_valuation = (
                        location_to.l10n_ro_property_stock_valuation_account_id.id
                    )
                if valued_type == "reception":
                    acc_src = acc_valuation

            # produsele din aceasta locatia folosesc pentru evaluare contul
            if location_from.l10n_ro_property_stock_valuation_account_id:
                # in cazul unui transfer intern se va face contare dintre
                # contul de stoc si contul din locatie
                if valued_type == "internal_transfer":
                    acc_src = (
                        location_from.l10n_ro_property_stock_valuation_account_id.id
                    )
                else:
                    acc_valuation = (
                        location_from.l10n_ro_property_stock_valuation_account_id.id
                    )

            # in Romania iesirea din stoc de face de regula pe contul de cheltuiala
            if valued_type in [
                "delivery",
                "consumption",
                "usage_giving",
                "production_return",
                "minus_inventory",
            ]:
                acc_dest = (
                    location_from.l10n_ro_property_account_expense_location_id.id
                    or acc_dest
                )
            elif valued_type in [
                "production",
                "delivery_return",
                "consumption_return",
                "usage_giving_return",
                "plus_inventory",
            ]:
                acc_src = (
                    location_to.l10n_ro_property_account_expense_location_id.id
                    or acc_src
                )
        return journal_id, acc_src, acc_dest, acc_valuation


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model
    def _create_correction_svl(self, move, diff):
        super(StockMoveLine, self)._create_correction_svl(move, diff)
        company_id = self.company_id
        if not self.company_id and self._context.get("default_company_id"):
            company_id = self.env["res.company"].browse(
                self._context["default_company_id"]
            )
        if not self.env["res.company"]._check_is_l10n_ro_record(company_id.id):
            return

        stock_valuation_layers = self.env["stock.valuation.layer"]

        for valued_type in move._get_valued_types():
            if getattr(move, "_is_%s" % valued_type)():

                if diff < 0 and "_return" not in valued_type:
                    valued_type = valued_type + "_return"
                if diff > 0 and "_return" in valued_type:
                    valued_type = valued_type.replace("_return", "")

                if valued_type == "plus_inventory_return":
                    valued_type = "minus_inventory"
                elif valued_type == "minus_inventory_return":
                    valued_type = "plus_inventory"
                elif valued_type == "internal_transfer_return":
                    valued_type = "internal_transfer"

                if hasattr(move, "_create_%s_svl" % valued_type):
                    stock_valuation_layers |= getattr(
                        move, "_create_%s_svl" % valued_type
                    )(forced_quantity=abs(diff))

        for svl in stock_valuation_layers:
            if not svl.product_id.valuation == "real_time":
                continue
            svl.stock_move_id._account_entry_move(
                svl.quantity, svl.description, svl.id, svl.value
            )
