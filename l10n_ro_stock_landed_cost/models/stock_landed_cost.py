from odoo import _, api, models
from odoo.exceptions import UserError


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"

    def button_draft(self):
        self.ensure_one()
        if self.company_id.l10n_ro_accounting and self.state == "done":
            self.account_move_id.button_draft()
            self.write({"state":"draft"})

    def button_validate(self):
        for rec in self:
            if rec.company_id.l10n_ro_accounting and rec.account_move_id:
                raise UserError(_(f"For Landed Cost = ({rec.id}, {rec.name}), you already have a Journal Entry. You can NOT revalidate. Create another Landed Cost (the reason is that you'll have old svl with this landed cost) "))
        return super().button_validate()
