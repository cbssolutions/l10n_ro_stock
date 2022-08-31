# Copyright (C) 2022 cbssolutions.ro
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move.line"
    
    l10n_ro_notice = fields.Boolean(
        related="picking_id.l10n_ro_notice",
        help="field form picking, just to be used in view",
    )

    @api.model
    def _get_valued_types(self):
        valued_types = super(StockMove, self)._get_valued_types()
        if not self.filtered("is_l10n_ro_record"):
            return valued_types

        valued_types += [
            "reception_notice",  # receptie de la furnizor cu aviz
            "reception_notice_return",  # retur receptie de la furnizor cu aviz
            "delivery_notice",
            "delivery_notice_return",
        ]
        return valued_types

    def _is_reception(self):
        """Este receptie in stoc fara aviz"""
        if not self.is_l10n_ro_record:
            return super(StockMove, self)._is_reception()

        it_is = (
            super(StockMove, self)._is_reception()
            and not self.picking_id.l10n_ro_notice
        )
        return it_is

    def _is_reception_return(self):
        """Este un retur la o receptie in stoc fara aviz"""
        if not self.is_l10n_ro_record:
            return super(StockMove, self)._is_reception_return()

        it_is = (
            super(StockMove, self)._is_reception_return()
            and not self.picking_id.l10n_ro_notice
        )
        return it_is

    def _is_reception_notice(self):
        """Este receptie in stoc cu aviz"""
        if not self.is_l10n_ro_record:
            return super(StockMove, self)._is_reception_return()

        it_is = (
            self.company_id.l10n_ro_accounting
            and self.picking_id.l10n_ro_notice
            and self.location_id.usage == "supplier"
            and self._is_in()
        )
        return it_is

    def _create_reception_notice_svl(self, forced_quantity=None):
        created_svl_ids = self.env["stock.valuation.layer"]
        for move in self.with_context(standard=True, valued_type="reception_notice"):

            if (
                move.product_id.type != "product"
                or move.product_id.valuation != "real_time"
            ):
                continue
            picking = move.picking_id
            date = picking.l10n_ro_accounting_date or picking.date
            price_unit = move.price_unit
            qty = move.quantity_done
            value = qty * price_unit
            product = move.product_id

            accounts = move.with_context(
                valued_type="invoice_in_notice"
            )._get_accounting_data_for_valuation()
            bill_to_recieve = move.company_id.l10n_ro_property_bill_to_receive.id
            if not bill_to_recieve:
                raise ValidationError(
                    _(
                        "Go to Settings/config/romania and set the property bill to receive to 408."
                    )
                )
            account_move = self.env["account.move"].create(
                {
                    "date": date,
                    "ref": f"Reception Notice for picking=({picking.name},{picking.id}), product={product.id,product.name}",
                    "journal_id": accounts[0],
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "account_id": accounts[3],  # 3xx
                                "product_id": product.id,
                                "name": product.name + f" ({price_unit}x{qty}={value})",
                                "quantity": qty,
                                "debit": value,
                                "credit": 0,
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "account_id": bill_to_recieve,
                                "product_id": product.id,
                                "name": product.name + f" ({price_unit}x{qty}={value})",
                                "quantity": qty,
                                "debit": 0,
                                "credit": value,
                            },
                        ),
                    ],
                }
            )
            account_move.action_post()
            svl = self.env["stock.valuation.layer"].create(
                {
                    "description": f"Notice reception picking=({picking.name},{picking.id})",
                    "account_move_id": account_move.id,
                    "stock_move_id": move.id,
                    "product_id": move.product_id.id,
                    "company_id": move.company_id.id,
                    "value": value,
                    "remaining_value": value,
                    "l10n_ro_bill_accounting_date": date,
                    "quantity": qty,
                    "remaining_qty": qty,
                    "unit_cost": price_unit,
                    "l10n_ro_valued_type": "reception_notice",
                }
            )

            created_svl_ids |= svl

        return created_svl_ids

    def _is_reception_notice_return(self):
        """Este un retur la receptie in stoc cu aviz"""
        if not self.is_l10n_ro_record:
            return False

        it_is = (
            self.company_id.l10n_ro_accounting
            and self.picking_id.l10n_ro_notice
            and self.location_dest_id.usage == "supplier"
            and self._is_out()
        )
        return it_is

    def _create_reception_notice_return_svl(self, forced_quantity=None):
        svl = self.env["stock.valuation.layer"]
        for move in self:
            move = move.with_context(
                standard=True, valued_type="reception_notice_return"
            )
            if (
                move.origin_returned_move_id
                and move.origin_returned_move_id.sudo().stock_valuation_layer_ids
            ):
                move = move.with_context(
                    origin_return_candidates=move.origin_returned_move_id.sudo()
                    .stock_valuation_layer_ids.filtered(lambda sv: sv.remaining_qty > 0)
                    .ids
                )
            created_svl = move._create_out_svl(forced_quantity)
            # we must also create a account_move for what was returned
            picking = move.picking_id
            product = created_svl.product_id
            accounts = product._get_product_accounts()
            accoutns2 = move._get_accounting_data_for_valuation()
            created_account_move = self.env["account.move"].create(
                {
                    "date": move.date,
                    "ref": f"Return for notice_reception picking=({picking.name},{picking.id}), product={product.id,product.name}",
                    "journal_id": accoutns2[0],
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "account_id": accounts["stock_valuation"].id,  # 3xx
                                "product_id": product.id,
                                "name": "Return for notice_reception" + f" qty={created_svl.quantity} value={created_svl.value}",
                                "quantity": created_svl.quantity,
                                "debit": 0,
                                "credit": abs(created_svl.value),
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "account_id": accounts["income"].id, # 7xx
                                "product_id": product.id,
                                "name": "Return for notice_reception" + f" qty={created_svl.quantity} value={created_svl.value}",
                                "quantity": created_svl.quantity,
                                "debit": abs(created_svl.value),
                                "credit": 0,
                            },
                        ),
                    ],
                }
            )
            created_account_move.action_post()
            created_svl.account_move_id = created_account_move.id
            svl += created_svl

            
        return svl

    def _is_delivery(self):
        """Este livrare din stoc fara aviz"""
        if not self.is_l10n_ro_record:
            return super(StockMove, self)._is_delivery()

        return (
            super(StockMove, self)._is_delivery() and not self.picking_id.l10n_ro_notice
        )

    def _is_delivery_return(self):
        """Este retur la o livrare din stoc fara aviz"""
        if not self.is_l10n_ro_record:
            return super(StockMove, self)._is_delivery_return()

        it_is = (
            super(StockMove, self)._is_delivery_return()
            and not self.picking_id.l10n_ro_notice
        )
        return it_is

    def _is_delivery_notice(self):
        """Este livrare cu aviz"""
        if not self.is_l10n_ro_record:
            return False

        it_is = (
            self.company_id.l10n_ro_accounting
            and self.picking_id.l10n_ro_notice
            and self.location_dest_id.usage == "customer"
            and self._is_out()
        )
        return it_is

    def _create_delivery_notice_svl(self, forced_quantity=None):
        move = self.with_context(standard=True, valued_type="delivery_notice")
        return move._create_out_svl(forced_quantity)

    def _is_delivery_notice_return(self):
        """Este retur livrare cu aviz"""
        if not self.is_l10n_ro_record:
            return False

        it_is = (
            self.company_id.l10n_ro_accounting
            and self.picking_id.l10n_ro_notice
            and self.location_id.usage == "customer"
            and self._is_in()
        )
        return it_is

    def _create_delivery_notice_return_svl(self, forced_quantity=None):
        move = self.with_context(standard=True, valued_type="delivery_notice_return")
        return move._create_in_svl(forced_quantity)

    def _romanian_account_entry_move(self, qty, description, svl_id, cost):
        res = super()._romanian_account_entry_move(qty, description, svl_id, cost)
        svl = self.env["stock.valuation.layer"]
        if self._is_delivery_notice():
            # inregistrare valoare vanzare
            sale_cost = self._l10n_ro_get_sale_amount()
            move = self.with_context(valued_type="invoice_out_notice")

            (
                journal_id,
                acc_src,
                acc_dest,
                acc_valuation,
            ) = move._get_accounting_data_for_valuation()
            move._create_account_move_line(
                acc_valuation, acc_dest, journal_id, qty, description, svl, sale_cost
            )

        if self._is_delivery_notice_return():
            # inregistrare valoare vanzare
            sale_cost = -1 * self._l10n_ro_get_sale_amount()
            move = self.with_context(valued_type="invoice_out_notice")

            (
                journal_id,
                acc_src,
                acc_dest,
                acc_valuation,
            ) = move._get_accounting_data_for_valuation()
            move._create_account_move_line(
                acc_dest, acc_valuation, journal_id, qty, description, svl_id, sale_cost
            )
        return res

    def _l10n_ro_get_sale_amount(self):
        valuation_amount = 0
        sale_line = self.sale_line_id
        if sale_line and salvalued_typee_line.product_uom_qty:
            price_invoice = sale_line.price_subtotal / sale_line.product_uom_qty
            price_invoice = sale_line.product_uom._compute_price(
                price_invoice, self.product_uom
            )
            valuation_amount = price_invoice * abs(self.product_qty)
            company = self.location_id.company_id or self.env.company
            valuation_amount = sale_line.order_id.currency_id._convert(
                valuation_amount, company.currency_id, company, self.date
            )
        return valuation_amount

    def _get_accounting_data_for_valuation(self):
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

            # in nir si factura se ca utiliza 408
            if valued_type == "invoice_in_notice":
                if location_to.l10n_ro_property_account_expense_location_id:
                    acc_dest = (
                        acc_valuation
                    ) = location_to.l10n_ro_property_account_expense_location_id.id
                # if location_to.property_account_expense_location_id:
                #     acc_dest = (
                #         acc_valuation
                #     ) = location_to.property_account_expense_location_id.id
            elif valued_type == "invoice_out_notice":
                if location_to.l10n_ro_property_account_income_location_id:
                    acc_valuation = acc_dest
                    acc_dest = (
                        location_to.l10n_ro_property_account_income_location_id.id
                    )
                if location_from.l10n_ro_property_account_income_location_id:
                    acc_valuation = (
                        location_from.l10n_ro_property_account_income_location_id.id
                    )

            # in Romania iesirea din stoc de face de regula pe contul de cheltuiala
            elif valued_type in [
                "delivery_notice",
            ]:
                acc_dest = (
                    location_from.l10n_ro_property_account_expense_location_id.id
                    or acc_dest
                )
            elif valued_type in [
                "delivery_notice_return",
            ]:
                acc_src = (
                    location_to.l10n_ro_property_account_expense_location_id.id
                    or acc_src
                )
        return journal_id, acc_src, acc_dest, acc_valuation