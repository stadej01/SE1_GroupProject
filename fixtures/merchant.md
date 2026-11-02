<!-- start: Node_Merchant_Greeting -->
# Node_Merchant_Greeting
<!-- category: shop, color: blue -->
<!-- REVIEW (Alex): Interleaved sequence: mutations execute after line 1, auto-jump evaluated after line 2. -->

Merchant: Ah, welcome back, traveler! <!-- #line:dlg_mrc_001 -->

[set: visited_merchant = true]
[set: talk_count = talk_count + 1]

Merchant: I've been organizing my stock all morning. <!-- #line:dlg_mrc_002 -->

[if talk_count > 5] <<jump: Node_Merchant_Annoyed>>

Merchant: What can I do for you today? <!-- #line:dlg_mrc_003 -->

* [if gold >= 50] "I'll buy the enchanted dagger (50 Gold)." -> Node_Buy_Dagger <!-- #line:chc_mrc_001 -->
* [if has_stolen_amulet == true] "I found your missing amulet!" -> Node_Hand_In_Quest <!-- #line:chc_mrc_002 -->
* "Just browsing your wares." -> Node_Browse_Shop <!-- #line:chc_mrc_003 -->
* "I must be going." -> Node_Exit <!-- #line:chc_mrc_004 -->

# Node_Merchant_Annoyed
<!-- category: shop, color: red -->
Merchant: You again? Buy something or leave. <!-- #line:dlg_mrc_010 -->
<<jump: Node_Exit>>

# Node_Buy_Dagger
<!-- category: shop, color: green -->
[set: gold = gold - 50]
Merchant: A fine choice. Anything else? <!-- #line:dlg_mrc_020 -->
* "Let me look around more." -> Node_Browse_Shop <!-- #line:chc_mrc_020 -->
* "That's all." -> Node_Exit <!-- #line:chc_mrc_021 -->

# Node_Hand_In_Quest
<!-- category: quest, color: purple -->
Merchant: My amulet! You have my thanks. <!-- #line:dlg_mrc_030 -->
<<jump: Node_Merchant_Greeting>>

# Node_Browse_Shop
<!-- category: shop, color: blue -->
Merchant: Take your time. <!-- #line:dlg_mrc_040 -->
* "Actually, let me talk to you." -> Node_Merchant_Greeting <!-- #line:chc_mrc_040 -->
* "Keep browsing." -> Node_Browse_Shop <!-- #line:chc_mrc_041 -->

# Node_Exit
Merchant: Safe travels. <!-- #line:dlg_mrc_050 -->
