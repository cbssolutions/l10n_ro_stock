# Copyright (C) 2022 NextERP Romania
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from ast import literal_eval
from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    # try to keep the stock value account 3xx at same value as stock_valuation
    # at setting to draft account_moves (invoices and not) that have valuation on them
    # can be the case of reception or + inventory
    # and than at posting

    _inherit = "account.move"


        
    def action_post(self):
        # post again of account_moves with svl ( before were set to draft)
        # the bills that have l10n_ro_bill_for_picking are not taken into consideration
        #    because is like in the case from the first posting the invoice
        # is for example case of a journal_entry for inventory_plus
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )

        for move in self.filtered(
            lambda r: r.is_l10n_ro_record and r.stock_valuation_layer_ids and not r.l10n_ro_bill_for_picking
        ):

            for svl in move.stock_valuation_layer_ids.filtered(lambda r: r.quantity):
                # we only take the svl that have qty on them, others are: landed cost, the move setting to draft
                text_error = (
                    f"For AccountMove:({move.ref},{move.id}) at "
                    f"product=({svl.product_id.name},{svl.product_id.id}) "
                    f"svl={svl} qty = {svl.quantity}"
                )
                if svl.quantity <= 0:
                    raise UserError(
                        _(
                            text_error
                            + f" svl quantity is less than 0, is a out move with value from stock. You are not allowed to do it because were modifed also other svl "
                        )
                    )

                text_error = (
                    f"For AccountMove:({move.ref},{move.id}) at "
                    f"product=({svl.product_id.name},{svl.product_id.id}) "
                    f"qty = {svl.quantity}"
                )
                accounts = svl.product_id._get_product_accounts()
                move_line = move.line_ids.filtered(
                    lambda r: r.product_id == svl.product_id and r.account_id == accounts["stock_valuation"]
                )
                if len(move_line) != 1:
                     raise UserError(
                        _(
                            text_error
                            + f" something is wrong. We should have one line with stock_account for this svl  "
                            f"svl={svl} move_line={move_line}"
                        )
                    )
                   
                line_qty = (
                    move_line.quantity
                )  # HERE I THINK I MUST CONVERT THE POSIBLE QTY IN PRODUCT QTY
                if not svl.remaining_qty:
                    raise UserError(
                        _(
                            text_error
                            + f" we do not have left any unit of quanty from this product  "
                            f"svl={svl}. You can not validate the invoice because is going to "
                            "create value in 3xx but with no product to add the value in stock"
                            " you can validate the only if you select a account diffrent than "
                            "product stocK_validation usualy 3xx"
                        )
                    )
                if svl.quantity != line_qty:
                    # can be also without this, but for modificatin is should not get here
                    raise UserError(
                        _(
                            text_error
                            + f" in bill line you have qty={line_qty} you have qty={svl.quantity }. "
                            "Quantities must be equal. If you can not see the qty is hiden :("
                        )
                    )
                balance = move_line.balance
                # we create a svl with new posted valuation 
                #( at draft the initial value is substrcted like it was never put)
                created_svl = svl.sudo().create(
                    {
                        "product_id":svl.product_id.id,
                        "account_move_id":move.id,
                        "quantity": 0,
                        "remaining_value": 0,
                        "value": balance,
                        "unit_cost": 0,
                        "company_id": svl.company_id.id,
                        "stock_valuation_layer_id": svl.id,
                        "l10n_ro_bill_accounting_date": move.date,

                    }
                )
                svl.write({"remaining_value": svl.remaining_value + balance,
                           "l10n_ro_bill_accounting_date": move.date,
                           "unit_cost": (svl.remaining_value + balance)/svl.remaining_qty,
                           })
                

        res = super().action_post()

        return res

    def button_draft(self):
        # we are are creating the oposite svl values, and set to original l10n_ro_draft 
        for move in self:
            if (
                move.is_l10n_ro_record
                and move.stock_valuation_layer_ids
                and move.state != "cancel"
            ):
                for svl in move.stock_valuation_layer_ids.filtered(lambda r: not r.l10n_ro_draft_svl_id and not r.l10n_ro_draft_svl_ids):
                    text_error = (
                        f"For AccountMove=({move.ref},{move.id}) at "
                        f"product=({svl.product_id.name},{svl.product_id.id}) "
                        f"svl={svl} qty={svl.quantity}"
                    )
                    to_do_error = (
                        "You are not allowed to put to draft this bill, "
                        "because is going to create difference between account 3xx and "
                        "stock value. Create a journal entry to fix what you need. "
                        "Or make the return and add a credit note."
                    )
                    if svl.quantity < 0:
                        raise UserError(
                            _(
                                text_error
                                + f" svl quantity is less than 0, is a out move with value from stock. You are not allowed to do it because were modifed also other svl (their value is taken from other svl). Make a inverse operation, or a manual journal entry."
                            )
                        )
                            
                    if move.move_type != "entry":
                        # is bill/invoice
                        if svl.quantity == 0: 
                            if svl.stock_valuation_layer_id and svl.stock_valuation_layer_id.remaining_qty <=0: 
                                raise UserError(
                                    _(
                                        text_error
                                        + f" Linked_svl={svl.stock_valuation_layer_id} quantity is less than 0." 
                                        + to_do_error
                                    )
                                )
                            elif not svl.stock_valuation_layer_id and svl.remaining_qty == 0 and svl.quantity ==0:
                                raise UserError(
                                    _(
                                        text_error
                                        + f" This was a manual SVL entry, that had modify the values of svl with stock when was added. Create the oposite svl entry" 
                                    )
                                )
                        
                        if svl.stock_valuation_layer_ids:
                            raise UserError(
                                _(
                                    text_error
                                    + f" you have more valuation layers={svl.stock_valuation_layer_ids}"
                                    + to_do_error
                                )
                            )
                        if svl.stock_valuation_layer_id:
                            svl_to_modify = svl.stock_valuation_layer_id
                        else:
                            svl_to_modify = svl
                        value = svl.value
                    else:
                        # is account_move with valuation from inventory plus
                        # it should be one product_id and svl per account_mvoe
                        if svl.quantity == 0:
                            if not svl.stock_valuation_layer_id:
                                raise UserError(
                                    _(
                                        text_error
                                        + " This is a Manual stock valuation that when"
                                        " was posted gave value to one or more svl. "
                                        "You can not set it to draft. Create another one." 
                                    )
                                )
                            else:
                                continue # is a value for stock that is going to be taken into account in next line
                        account_move_line_qty = move.line_ids.filtered(lambda r: r.product_id == svl.product_id)[0].quantity
                        if svl.remaining_qty != account_move_line_qty:
                            raise UserError(
                                _(
                                    text_error
                                    + f" svl remaing quantity is less than the quantity form product line={account_move_line_qty}."
                                    "You can not set to draft this entry - recreate a inventoy" 
                                )
                            )
                            
                        svl_to_modify = svl
                        # we can have also some manual valuations, and set to draft and than posted
                        # we are making sum of all the values from this account_entry 
                        # to let remaing_value fom other operations unchanged
                        value = sum((svl.stock_valuation_layer_ids + svl).mapped("value"))
                    
                    # we are creating a svl with the value of entry that was set to draft
                    corected_svl = svl.create(
                        {
                            "description": f"Setting to draft inv=({move.id},{move.name})",
                            "remaining_value": 0,
                                "account_move_id": move.id,
                                "product_id": svl.product_id.id,
                                "company_id": svl.company_id.id,
                                "unit_cost": 0,
                                "value": -1 * value,
                                "remaining_value": 0,
                                "quantity": 0,
                                "remaining_qty": 0,
                                "l10n_ro_bill_accounting_date": svl.l10n_ro_bill_accounting_date,
                                "l10n_ro_valued_type": svl.l10n_ro_valued_type,
                                "stock_valuation_layer_id":svl_to_modify.id,
                                "l10n_ro_draft_svl_id":svl.id,
                        }
                    )
                    
                    svl_to_modify.write({"remaining_value":svl_to_modify.remaining_value - value,
                                         "unit_cost":(svl_to_modify.remaining_value - value)/svl_to_modify.remaining_qty if svl_to_modify.remaining_qty else 0} )
        
        
        return super().button_draft()
