The module is for reception/devlivery of products without invoice.
In picking fields 
        - l10n_ro_notice menas that is stock that does not have invoice and will be done later.
        - l10n_ro_accounting_date if notice  the date of created svl and account_moves.

At reception or delivery we have also a price_unit per product.
This price_unit will create svl and accounting Journal Entries ( for each product)
Created journal entries will have the account 408/418 invoices to make/recive

! Ff you done a mistake at a notice reception ( price, date), you can modify the generated account_moves form svl per picking
! you are doing this by setting to draft and post it again
! by doing this it will not change values from picking, but the changes will be visible in svl

At the receiving of a bill or creating a invoice you can set the notice pickings; 
if this is the case you'll have acocunt_mvoe_lines with account 408/418 and if a price 
difference will create another line with price idfference

In case (not probable) of reciving a invoice that have part of a notice (aviz), do not use the notice_pickings_ids field and modify the account_move_lines in bill.


 
It will create a landed cost with a "Price Difference" product available in the configuration.
Primirea marfurilor pe baza de aviz de insotire:
371 = 408       300.000 lei

Primirea facturii:
% = 401         357.000 lei
408                   300.000 lei
4426                      57.000 lei
+ line diferente

