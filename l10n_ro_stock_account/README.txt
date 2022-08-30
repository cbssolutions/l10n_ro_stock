With this modue for Romanian companies:

If a product is sorable and has valuation_type automatic, based on source and destination of the stock_move, 
    (receptions, deliveries, consume, usage_giving, inventory and  production) we are going to create
    accounting entries and stock_valuation

For a product that has valuation_type manual we do not create any svl or accounting entries because is suposed 
from time to time to make the inventory and put in accounting a entry based on it

For consumable products we are not going to make stock_valuation_entries at moves because when they enter, 
    is creded a consumed journal entry no stock_account is modified,
    and vhen we use/sell them we just make income, 


In Romania, the products get into stock with supplier invoice/bill ( and svl is created based on the values from bill).
Another case is when the products are geting into stock with a value (picking type notice) and after a time is coming the bill - is covered in l10n_ro_stock_notice module

At a validatin of reception that does not have l10n_ro_is_notice will create a svl recived qty and value of 0.
If the puchase module is instaled is going also to press the button on purchase order to create the bill and will have l10n ro bill for picking the validation picking

If a invoice has l10n_ro_bill_for_picking at validation is going to:
  - verify if the producst form reception ar in picking   - if not error
  - verify if is the same recived qty - if not error
  - if in svl still exist qty, the invoice will create a svl that is giving aditional value to what remain
  - if no qty exist in stock - instead on incresing the 3xx account will create a consume account line
  



On companies that have partner_id.country= romania is setting 
"l10n_ro_accounting": True,
"anglo_saxon_accounting": True,        # the check is anglo_saxon_accounting, but romanian accounting is a mix     
"l10n_ro_stock_acc_price_diff": True,

In location we have 
l10n_ro_property_account_income_location_id
l10n_ro_property_account_expense_location_id
l10n_ro_property_stock_valuation_account_id
 and if set will overwrite the accounts set on product if it has l10n_ro_stock_account_change
 
 Contraint on product to have stock_input = stock_output = stock_val
 
    
In stock_valuation_layer we are adding
    l10n_ro_valued_type   # just a name we can live also without
    l10n_ro_bill_accounting_date  This is the date from billing accounting date. The bill that generate this svl

in stock_move_line
    mthod _create_correction_svl    
    
in stock_move


!!!!!!!!!!!! if something is wrong in svl, go in inventory/reporting/inventory valuation, search for the product
and in grouped product you have a + is going to open action_revaluation that is letting you add a line for that product
that will change the remaining_value at svl with remaining_qty ( and creates also a accouting entry)
You can create a reverse entry for accounting entry (account_move) and you will create a difference between 3xx account and the value of stock (svl).
In general, the account_move that do not have a valuation are creating diffence between 3xx and svl


TEST CASE:
A. RECEPTION: (cost price 9.1  9.2 9.3 9.4)

A1. picking:    p91  x 10units   & p92  X 20units& p93 x 30 units   p94 cosumable      date today
svl for p91, p92, p93 with received qty and value of 0

till the inovie  p91 remaining qty 0, p92 remaing qty 4, p 93 remaing qty 30
what we deliver from this reception is going to get out with a value of 0 ( because we did not record the invoice in odoo, and does not know any cost)

A2. invoice: it must have the picking as l10n_ro_bill_for_picking   ( is the field that is telling odoo for what picking is this inovice.)
is going to verify picking vs invoice lines and qty to be the same, if not will raise error

invoice     p91   10lei    p92  12lei   p93  13 p94 14  accounting_date yesterday
accounting lines   6xx  debit 100lei ( p91)     3xx debit 240 (p92)    3xx debit 390 (p92)  6xx debit 420
new svl (with account_move_id the invoice) for p92 with stock_valuation_layer_id (linked to reception svl) will recive a qty 0 with value of 240 => unit_value =240/4 = 60
new svl for p93 with qty=0 and value of 390 => now p93 from stock have a unit value of 13

A3. we deliver 2 x p92  and 10 x p93  
=> svl with -qty and price with accounting_entries that are p92: debit 3xx 120  p93: debit 3xx  130

B. Setting to draft of a account_move (invoice or accounting entry) that has svl:
B1 if remaining_qty
- will create with same account_move_id a svl with minus that value and modify the svl with qty remaining_qty 
    to be able to set to draft/post multiple times in svl exist a field l10n_ro_is_draft that is true at svl created from setting to draft
B2 if no remaining_qty (and has svl_value ) it will not let you setting it to draft because it can not put back the svl value 

C. Return of a reception ( delivery of what was recived that can have other prices becuase landed cost, or already deliverred and returned others ..) reception_return
C1. svl with out qty and what price it found. Is making a account_move with minus that qty (like when is inventory los)
for each svl will create a posted account entry with credit in 3xx with value of products that were taken for return

!!!!!!!!!!!   Vendor Credit Note  for a purchase (bill) must be with accounts of consume not 3xx ( becuse is posible that we didn't return the same products and other can have diffrent prices. at return their value was taken out of stock)


C1a. if they set to draft the reception invoice is going to modify the value of remaining qty
C1b. if they are going to create a inverse invoice, this one must decrese the value of remaining svl 

D. Scrap of a reception  = minus inventory  is creating a svl (with qty and what price is finding in stock) and account_move with value



E. Delivery
At delivery picking ( sendig the products) is making a svl and account_move with the values from stock 3xx is decreasing
At invoicing is only going to make revenue
F. Delivery return  
At return delivery picking is going to create a svl with exactly the same values that were send, and a account_move with 3xx increasing


G.Inventory plus = will create a svl and account_move with the cost price that is set on product
You can modify the value/date of inventory by setting to draft and reposted it

H. Inventory minus = like D. ( scrap of a reception)

I. Consumtion = transfer to consumption location ( location type consume)
Is like a delivery = like E. (is creating svl and account_move with qty and value)
I.1. Consumtion return = like F.

J. usage_giving Darea in folosinta like Delivery E. return the same as F



!!!!!!!!! in this module is also the code for keeping the value of stock in concordanse with account_moves
!!!!!!!!!! when you set to draft a journal_entry/bill and then reposting it
!!!!!!!!!! it has code also for draft/posing landed cost journal entries


l10n_ro_location_dest_id  on stock_valuation_layer is giving you also the value of stock in different locations
in inventory/reporting/inventory valuation with a filter on remaing_qty and different grouping you can see any stock value that you want

