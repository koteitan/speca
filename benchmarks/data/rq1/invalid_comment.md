#16
Keeping this as invalid since the team doesn’t plan to fix it.

#18
This is a logical bug in a dead code path that is never executed. Although the code indeed contains a bug, it has no impact on the actual network or client behavior, so invalid is appropriate.
get_data_column_sidecars() was already unused by that time, and https://github.com/status-im/nimbus-eth2/pull/7511 removes the function entirely. The PR post-dates this report by some days, but doesn't have to remove any usage of it, because it doesn't exist. The PoC has to manually call get_data_column_sidecars() precisely because there's no way to access it otherwise.

#51
Client comments:

This is a design choice for performance (O(1) lookups with HashSet) and simplicity. This result is stored internally and is fully encapsulated within lighthouse, i.e. no impact on functionality and not exposed externally.

See discussion here:
https://github.com/sigp/lighthouse/pull/7711#issuecomment-3157508418

#53
Erigon CL is out of scope, only the EL side was in scope, so invalid

#56
Client comments:

is an informational at best.

"State root divergence on/after the Fulu upgrade if a mis-sized vector slips in." "That makes a mis-size unlikely today, but the upgrade path’s lack of validation is still a consensus foot-gun." "Mock a malicious/buggy InitializeProposerLookahead that returns wrong length"

I doubt they'd be able to trigger this outside of some unrealistic test case.

Planning to keep this as info.
The issue is not going to be fixed, so will be invalidated unless fixed.

#64
Agree that the public disclosure occurred before the issue submission. Planning to keep this as invalid.

This bug was noted in a public discord conversation before the report:

https://discord.com/channels/595666850260713488/598292067260825641/1418242503261552801

#92
EL is trusted.

A compromised or buggy execution endpoint could still feed reordered blobs

is not a valid assumption. Planning to keep as invalid.

#94
Agree with protocol judging. According to the specification defined in EIP-7892:

BLOB_SCHEDULE only contains two fields: EPOCH and MAX_BLOBS_PER_BLOCK.

TARGET_BLOBS_PER_BLOCK and BASE_FEE_UPDATE_FRACTION should not appear in the CL’s BLOB_SCHEDULE. Therefore, if a CL client detects these extra fields when loading the configuration and rejects it, this is the correct behavior — not a bug.

#107
From Geth team:

invalid: We are checking the TxGasLimit not in the engine API but deeper in the stack during the actual execution of the block here: https://github.com/ethereum/go-ethereum/blob/2872242045377abe1ec9a54b8bc874dc2bb4febd/core/state_transition.go#L330

#121
This is an issue in unused code. Planning to keep as invalid.

#154
Agree with the protocol team’s judgement. The correct ForkDigest function should be: https://github.com/OffchainLabs/prysm/blob/08be6fde92aef248980d27cc8c522d328cded6f6/config/params/fork.go#L23

This issue was submitted without a PoC. So invalid is appropriate.

#211
We agree with the protocol team’s judgement. As noted, this is a known issue and may be addressed if support for this endpoint beyond the spec becomes necessary.

#222
Keeping as invalid due to contest rules:

Informational issues are valid if they don't lead to a sufficient impact to count as Low or higher and are valuable enough for the client that they decided to implement the change in the code.

It is invalid, based on the following:

Doesn't make sense, we still count those requests in our rate limiter and will throttle them. Requesting data columns we don't have because they are outside of MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS to DoS the node doesn't make sense, you would rather request data we have as it adds more burden to the node.

From code perspective it makes sense to check MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS but this has no impact and does not open a attack surface in any way.

#239
Keeping as invalid due to contest rules:

Informational issues are valid if they don't lead to a sufficient impact to count as Low or higher and are valuable enough for the client that they decided to implement the change in the code.

#250
Agree with the protocol team’s judgement. This type of validation should be performed on the EL side.

From the nimbus team:

A length check isn't incorrect, but it's neither a necessary nor sufficient check. A faulty execution client could just as easily "slip unverifiable data columns past Nimbus" of the correct length, but by design of the engine API (especially getBlobsV2; that's its entire point, to avoid CL verification overhead) the CL should not waste resources checking this.

A faulty execution client should be fixed, not patched around by the CL.

#264
Unfortunately, submission #243 was made earlier than this issue(#264). According to the contest rules, only the first submitted info is considered valid. If this issue cannot be H/M/L in severity, we can only keep it as invalid.

#282
Too abstract and lacks sufficient evidence. I don’t see any connection between the “OpenZeppelin audit of Mantle’s implementation” and Besu’s secp256r1 implementation.

#317
This issue was not introduced in Fusaka. So we consider it OOS.

#331
The execution layer is trusted. It's intended design that data from EL is not verified as it's considered trusted. Additionally, the checks from EIP are done by EL.

#389
This is invalid as EL is assumed trusted and it's intended not to check the date from the execution layer as it would make the process too slow.

