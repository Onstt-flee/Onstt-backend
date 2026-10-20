"""Fail-closed audit for feedback-v0.3 and its operational-shadow follow-up."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024
DEFERRED_PI_PATHS = {
    "deployment/feedback-staging/finalize-runtime-pairs.sh",
    "deployment/judgment-pi5/run-feedback-pairs-50.sh",
    "evaluation/feedback/RUNTIME_PAIR_INTAKE.md",
    "tests/test_pi5_deployment_templates.py",
}
CHECKPOINT_ROOT_FILES = {"README.md", "PROGRESS.md"}
CHECKPOINT_PREFIXES = (
    "analyzer/feedback_contract.py",
    "analyzer/feedback_particle_risk_gate.py",
    "analyzer/feedback_two_stage_contract.py",
    "analyzer/feedback_service.py",
    "analyzer/feedback_store.py",
    "analyzer/feedback_worker.py",
    "analyzer/feedback_admin.py",
    "deployment/feedback-staging/",
    "docs/MODEL_SYSTEM_STATUS_2026-10-15.md",
    "evaluation/feedback/HOLDOUT_V0.4_SEAL.md",
    "evaluation/feedback/build_holdout_v0_4.py",
    "evaluation/feedback/build_holdout_v0_5.py",
    "evaluation/feedback/build_holdout_v0_6.py",
    "evaluation/feedback/build_holdout_v0_7.py",
    "evaluation/feedback/build_holdout_v0_8.py",
    "evaluation/feedback/build_holdout_v0_9.py",
    "evaluation/feedback/build_holdout_v0_10.py",
    "evaluation/feedback/build_holdout_v0_11.py",
    "evaluation/feedback/build_synthetic_shadow_v0_1.py",
    "evaluation/feedback/build_existence_particle_diagnostic_v0_1.py",
    "evaluation/feedback/build_existence_particle_diagnostic_v0_2.py",
    "evaluation/feedback/build_particle_risk_adversarial_v0_1.py",
    "evaluation/feedback/compare_runs.py",
    "evaluation/feedback/evaluate_particle_risk_gate.py",
    "evaluation/feedback/evaluate_particle_risk_adversarial.py",
    "evaluation/feedback/existence_particle_diagnostic_v0.1",
    "evaluation/feedback/holdout_v0.4",
    "evaluation/feedback/holdout_v0.5",
    "evaluation/feedback/holdout_v0.6",
    "evaluation/feedback/holdout_v0.7",
    "evaluation/feedback/holdout_v0.8",
    "evaluation/feedback/holdout_v0.9",
    "evaluation/feedback/holdout_v0.10",
    "evaluation/feedback/holdout_v0.11",
    "evaluation/feedback/particle_risk_gate_v0.1.result.json",
    "evaluation/feedback/particle_risk_adversarial_v0.1",
    "evaluation/feedback/model_policy_v0.1.result.json",
    "evaluation/feedback/runner.py",
    "evaluation/feedback/existence_particle_diagnostic_v0.2",
    "evaluation/feedback/reparse_run.py",
    "evaluation/feedback/actual_shadow_v0.1",
    "evaluation/feedback/shadow_v0.1",
    "evaluation/feedback/two_stage_",
    "scripts/audit_feedback_v0_3_checkpoint.py",
    "scripts/build_feedback_actual_inputs.py",
    "scripts/diagnose_feedback_failed_stages.py",
    "scripts/run_feedback_actual_shadow.py",
    "scripts/run_feedback_synthetic_shadow.py",
    "scripts/run_feedback_worker.py",
    "scripts/run_feedback_worker_process_crash_drill.py",
    "scripts/run_feedback_worker_recovery_drill.py",
    "scripts/validate_feedback_model_policy.py",
    "scripts/verify_feedback_admin_shadow.py",
    "scripts/verify_feedback_admin_http.py",
    "tests/test_feedback_",
    "training/feedback/FEEDBACK_V0.3_",
    "training/feedback/FEEDBACK_V0.4_",
    "training/feedback/FEEDBACK_V0.5_",
    "training/feedback/FEEDBACK_V0.6_",
    "training/feedback/FEEDBACK_V0.7_",
    "training/feedback/FEEDBACK_V0.8_",
    "training/feedback/FEEDBACK_V0.9_",
    "training/feedback/FEEDBACK_PARTICLE_RISK_",
    "training/feedback/FEEDBACK_RESEARCH_FREEZE_",
    "training/feedback/FEEDBACK_TWO_STAGE_",
    "training/feedback/HOLDOUT_V0.7_",
    "training/feedback/HOLDOUT_V0.8_",
    "training/feedback/HOLDOUT_V0.9_",
    "training/feedback/HOLDOUT_V0.10_",
    "training/feedback/HOLDOUT_V0.11_",
    "training/feedback/config_v0.4.json",
    "training/feedback/data/eval_v0.4.chatml.jsonl",
    "training/feedback/data/feedback_v0.4",
    "training/feedback/data/train_v0.4.chatml.jsonl",
    "training/feedback/generate_v0_4.py",
    "training/feedback/config_v0.5.json",
    "training/feedback/data/eval_v0.5.chatml.jsonl",
    "training/feedback/data/feedback_v0.5",
    "training/feedback/data/train_v0.5.chatml.jsonl",
    "training/feedback/generate_v0_5.py",
    "training/feedback/config_v0.6.json",
    "training/feedback/data/eval_v0.6.two-stage.chatml.jsonl",
    "training/feedback/data/feedback_v0.6.two-stage",
    "training/feedback/data/train_v0.6.two-stage.chatml.jsonl",
    "training/feedback/generate_v0_6_two_stage.py",
    "training/feedback/config_v0.7.json",
    "training/feedback/data/eval_v0.7.stage1-comparison.chatml.jsonl",
    "training/feedback/data/feedback_v0.7.stage1-comparison",
    "training/feedback/data/train_v0.7.stage1-comparison.chatml.jsonl",
    "training/feedback/generate_v0_7_stage1_correction_comparison.py",
    "training/feedback/config_v0.8.json",
    "training/feedback/data/eval_v0.8.stage2-recovery-style.chatml.jsonl",
    "training/feedback/data/feedback_v0.8.stage2-recovery-style",
    "training/feedback/data/train_v0.8.stage2-recovery-style.chatml.jsonl",
    "training/feedback/generate_v0_8_stage2_recovery_style.py",
    "training/feedback/config_v0.9.json",
    "training/feedback/data/eval_v0.9.stage2-contract-stability.chatml.jsonl",
    "training/feedback/data/feedback_v0.9.stage2-contract-stability",
    "training/feedback/data/train_v0.9.stage2-contract-stability.chatml.jsonl",
    "training/feedback/generate_v0_9_stage2_contract_stability.py",
    "training/feedback/config_v0.3.json",
    "training/feedback/data/eval_v0.3.chatml.jsonl",
    "training/feedback/data/feedback_v0.3",
    "training/feedback/data/train_v0.3.chatml.jsonl",
    "training/feedback/generate_v0_3.py",
    "training/judgment/train_lora.py",
)
PROHIBITED = (
    ".env", "*.db", "*.sqlite3", "*.safetensors", "*.gguf", "*.bin",
    "*.pt", "*.pth", "*.wav", "*.mp3", "evaluation/feedback/runs/*",
    "evaluation/feedback/intake/*",
)
KEY_HASHES = {
    "evaluation/feedback/holdout_v0.4.jsonl": "c22c5ddb0153c60d7087ef1e26580e669ea974e2bdafb0e65142f9eaeed60802",
    "evaluation/feedback/holdout_v0.4.protocol.json": "24d7d692faf8994da7dc3779f3e9f0eb8da60bfca7b3d82fbd2559fb8a533d94",
    "evaluation/feedback/holdout_v0.4.result.json": "a047f090d23c199d5186b2c636e0361705541abd42c40bfdcd49fe5efb10cfd7",
    "training/feedback/config_v0.3.json": "998a7a8d89dee594780a5a2aa2a03ee3059e34836609c943b2c626aca0457bef",
    "training/feedback/data/feedback_v0.3.jsonl": "fca3ba047ffc5c19b2af5a3c515538bfda22ae92e50b0d5c3d611ee643a8d196",
    "evaluation/feedback/shadow_v0.1.inputs.jsonl": "495a2c2b07a542422161b76b3377733ad12cb301283402b7aec97444cce03d27",
    "evaluation/feedback/shadow_v0.1.result.json": "4e22d092b19dc889e01cf0a28a1237131bda56d82ad5a9d6d391fa755809ca3d",
    "evaluation/feedback/shadow_v0.1.admin.result.json": "bd0b91c55d565f0b80cdfe9b691cb265473efcef3ce5b48d736f5e4747971f72",
    "evaluation/feedback/shadow_v0.1.admin-http.result.json": "5b96156811f88948e3431c8b47281ba8670ed1e01781e626d5de6f8bccc4ef72",
    "evaluation/feedback/shadow_v0.1.worker-recovery.result.json": "3bdfadb9cfb0aefe18f4b540ca6089a2aafdd7d6b0cfe74d0042485640b60213",
    "evaluation/feedback/shadow_v0.1.worker-process-crash.result.json": "9aebca946465ed31d8a124e63bdbc774896b92097bfb857b201cc5dbd8c8cb16",
    "evaluation/feedback/actual_shadow_v0.1.inputs.manifest.json": "a19f97f42cf2c510fe055b183104bdc464519adb8e89ddeb5b5ab3cd3cb9643f",
    "evaluation/feedback/actual_shadow_v0.1.result.json": "c05d498ba42dc18a54bdfb7c1b6b5be9011b1740de2bb49f139bae1305e0af46",
    "evaluation/feedback/actual_shadow_v0.1.v08.result.json": "b3ac3767fa6fa0cf19e30f89d84fa25a968e1d35a79484490859fd83bed2c0c5",
    "evaluation/feedback/actual_shadow_v0.1.v08.failure-diagnostic.json": "084c00c0533cdc54c0b988b45fe02cb2f3a17db2a4dd610ef9cb4657a8771fa1",
    "evaluation/feedback/actual_shadow_v0.1.admin.result.json": "bfa9cab1cbe7fe34412bfa2bcda52b1d167bdb0f7537e71d349fac40f2d96a0c",
    "evaluation/feedback/actual_shadow_v0.1.admin-http.result.json": "e0cf27040c809325ac5924e5fa8239a9e0b496888b53147edfa78534a9535d6b",
    "evaluation/feedback/holdout_v0.4.baseline-lora.result.json": "8d402b24478793bf3d782129763e10428914fafefa3b370d838c85aedb0494ac",
    "evaluation/feedback/existence_particle_diagnostic_v0.1.jsonl": "74f2d76f96c79ad942dd682157cd6520287b0cfc78c4a7aa490ca8d02d0dcd9e",
    "evaluation/feedback/existence_particle_diagnostic_v0.1.manifest.json": "842886702bd91d2dcb96fa58242b7d5a4465cf0f306de76ca842a96b9aa911e8",
    "evaluation/feedback/existence_particle_diagnostic_v0.1.protocol.json": "3fb22de6fde24c3981512922d02a3fd523c09a72ef370c45a1b38717641f8901",
    "evaluation/feedback/existence_particle_diagnostic_v0.1.result.json": "91196f37c27ae009eeed88d04b44f3f0da99c79b6da29d17049f9056e76fe523",
    "evaluation/feedback/existence_particle_diagnostic_v0.2.jsonl": "60f884018586b4ccfcbb7786f85fa37f90d62bd6ab5d7ef13ada8b40110ce6d8",
    "evaluation/feedback/existence_particle_diagnostic_v0.2.manifest.json": "b39827f49c984cacb1a8f2c97c03578efd84e2897fdee83c8ed93917b4aede8a",
    "evaluation/feedback/existence_particle_diagnostic_v0.2.protocol.json": "862efbec8677abb3d7cf526ced4cee9ff07d7122cb9f2cdf1518ed811226230c",
    "evaluation/feedback/existence_particle_diagnostic_v0.2.result.json": "c04c0f08b44688524c1d5efac8cbd17234bdf89e33a6fba4afe3e0490e9b19e7",
    "evaluation/feedback/holdout_v0.5.jsonl": "b41e4ee0553e57051c7381c95151a885ffb41979a408078e8923f723352d59fc",
    "evaluation/feedback/holdout_v0.5.manifest.json": "51f015dc2a20227a6b7d460aac2ad977559c221fddac20a6d6747a24de645ad4",
    "evaluation/feedback/holdout_v0.5.protocol.json": "5b5e10e74fd64698907e3dc726b792a2777c232bc45034ab8fa154a0c6e13de5",
    "evaluation/feedback/holdout_v0.5.baseline-lora.result.json": "ca8a1a5bde8e235bea7b6ad3fc6fb6259a32e39787cc5749895b8802b0825d38",
    "training/feedback/config_v0.4.json": "bc09eed0b73265a610cb5ac291109248fff59f6de6dd8a458246f20b1c8e3e53",
    "training/feedback/data/feedback_v0.4.jsonl": "b9bee0df8d341e83d96d1475e07a15c095cd3ef89ae9ef009f56669cc008cd8c",
    "training/feedback/data/train_v0.4.chatml.jsonl": "e85bfa7e2f1fbf0479f609b66b77d4cda186f179f40a93ff5ab7a456b20c048b",
    "training/feedback/data/eval_v0.4.chatml.jsonl": "249fcc0c62c5cfb63d94fecd512954d45d09b771909c77f205550e64938c24d7",
    "training/feedback/data/feedback_v0.4.manifest.json": "3eba228be03a43fc2ad00623bf68712fadea0785d7c27e6267a04f40910a0d37",
    "evaluation/feedback/holdout_v0.6.jsonl": "104e0811b89843debb8d9e2e9b3be337cbf528918f85606a88b17b622bef1581",
    "evaluation/feedback/holdout_v0.6.manifest.json": "9333797dfdcce9bdb75f1fc4f12e4955f3722db719dee07e2b526dca577e2499",
    "evaluation/feedback/holdout_v0.6.protocol.json": "b56c03a55c40be983a777d56bca5996a9a92f9351a42777255c7cedd8a7097ff",
    "evaluation/feedback/holdout_v0.6.baseline-lora.result.json": "a7ad770a6487f864b3b8821bfec005fa6b1290ac2701380a43cb859f076d8f8f",
    "training/feedback/config_v0.5.json": "cac379894927b87c9151b621a184a1ddab75532c13ff98cf62d920ceb773ec2d",
    "training/feedback/data/feedback_v0.5.jsonl": "991bb71e8a9115cb1b18f786f18636cd0c6e693790d16a7c22b37fb9b7b6220a",
    "training/feedback/data/train_v0.5.chatml.jsonl": "7684f1e6707da0def1e7ef603d3dbca84d79cd38e7c938a5f5ce37db1c1c2211",
    "training/feedback/data/eval_v0.5.chatml.jsonl": "e1fbc503a2016df6994e03bf816769b5fe77ba3de30bd8e3526874e7b9fb9fe9",
    "training/feedback/data/feedback_v0.5.manifest.json": "f8cc618e823e9fca85032116f5016ca9ef832a3c03955a7984d6b452a8a23edc",
    "evaluation/feedback/particle_risk_gate_v0.1.result.json": "1cac1a5a6d2aaec7a57a35d5a318a01aef002c74f7bb36ab0672246c785e5578",
    "evaluation/feedback/particle_risk_adversarial_v0.1.jsonl": "d08058fc74c5b53fddf730e5f6a9bb11affb4a595e0df4738252bdd82519bafa",
    "evaluation/feedback/particle_risk_adversarial_v0.1.manifest.json": "631a809a7eac03482cdff1ebb4dd7c8c354ad3f9fc8709a599851b531b72a9fd",
    "evaluation/feedback/particle_risk_adversarial_v0.1.protocol.json": "6c7febb9ab5aaafaed76f509c5c78880c95bcdbbfce5e486986f14030aeda68e",
    "evaluation/feedback/particle_risk_adversarial_v0.1.result.json": "f77600502b4e05ea87c1e9cbb1fb03da7c2698a867353c54cb229dfb0e9128a6",
    "deployment/feedback-staging/model-policy.json": "110ef838dace599e42f3f1d2c131292cfdbcb5e3970e96da4344dadd0bc2cdac",
    "evaluation/feedback/model_policy_v0.1.result.json": "f768a82da7ab0e1413f0c679b6aa7fdd00f610b4dba4704bffba58a64d99d870",
    "evaluation/feedback/holdout_v0.7.jsonl": "e928c104a39623891dc41d9fcc8ed285517594d9eea417662cdc91235f84e6ab",
    "evaluation/feedback/holdout_v0.7.manifest.json": "91dbc335db08d65ef7a7f7bf77665853d568c7df32f701b6cb6536ea68100c66",
    "evaluation/feedback/holdout_v0.7.protocol.json": "f07ca0feb36deca11521a70d5e22f39deab2e1f56a4f9f528fd4e0e3936309d7",
    "evaluation/feedback/holdout_v0.7.execution-plan.json": "f65313e0a629619e13edf918bf7868c13e828b7eed74d1f84bade0d0741288b6",
    "evaluation/feedback/holdout_v0.7.execution-record.json": "afca33c28d88ad8b4ae5486444d4b3974cb8c673fd850fb3827d50b9ea377674",
    "evaluation/feedback/holdout_v0.7.result.json": "213e2249df1d12f545bf90af159790a0085e2ea6376a6d78d01f12e6f2790198",
    "evaluation/feedback/holdout_v0.8.jsonl": "541b8cd0cccfbb5fd9c8e7a63fcbe2174871472fb6e635c841387198ced7a16d",
    "evaluation/feedback/holdout_v0.8.manifest.json": "da19d1a44618e4814021053428ba23356d0a67a22e2f8a89045bf1c9042d972e",
    "evaluation/feedback/holdout_v0.8.protocol.json": "3d876bffc4369e6fa5872ee5996ad35d0609e17f61a2d4ed6b7f73e41ad9c122",
    "evaluation/feedback/holdout_v0.8.execution-plan.json": "a4fdfe9ff87947cc2371efa13f6b84994faafc992d74ebf662f6b7741b02b4e6",
    "evaluation/feedback/holdout_v0.8.result.json": "d9fa2625a75bd82ceefa33d06989e02db92f2225b42cab7cd2c4581db53c5491",
    "evaluation/feedback/holdout_v0.8.execution-record.json": "8d900b5e5306cf951a8d1b6ad50c73d8300623a87f1209c9c389c1f7d2bd69fe",
    "evaluation/feedback/holdout_v0.9.jsonl": "8582052baeece84b67e6afd44f167deff71ae275eac68fe61c5f77fe7ea1df48",
    "evaluation/feedback/holdout_v0.9.manifest.json": "c0d319a44ebb222e51c1c339eb30265e3eebc11e6629d6fe438f3e373dd39475",
    "evaluation/feedback/holdout_v0.9.protocol.json": "8188843331fab81ccfb4b1cd76ad4151f939fcf78ba52e7827d2803c02bad963",
    "evaluation/feedback/holdout_v0.9.execution-plan.json": "1defe7d51776354a452eeab2d79e8adbed6dfedd4f23f4736d0e2384115e1862",
    "evaluation/feedback/holdout_v0.9.execution-record.json": "31ea3cef56326d89827f00de748b6ae285a17a2321f879e973a5f4a89d823d21",
    "evaluation/feedback/holdout_v0.9.result.json": "8bc963bff8d439bac8a98b48284c9ac74247f8d2783ba344320f77b8f7f260c4",
    "evaluation/feedback/holdout_v0.10.jsonl": "a3457b98022971afbed368b647a1801284069d1857a886a02151e3c382e186c1",
    "evaluation/feedback/holdout_v0.10.manifest.json": "a518dd8428b71b806e3eab1ba3527062936ec1a2a2b316ccff37aee22028b119",
    "evaluation/feedback/holdout_v0.10.protocol.json": "d21c28079ae4c6b85a24d07ca86b146ecfe40e8ac5b1fbfdf45ae24d220b9f95",
    "evaluation/feedback/holdout_v0.10.execution-plan.json": "25c91711a89d1c8663127705b6a94111265e281eedfc17327ad88b89fde52c3e",
    "evaluation/feedback/holdout_v0.10.execution-record.json": "8e6fd1998900bf0092f6f695642ec4c40adab43803f80b0c39c446dc6a2f6e1e",
    "evaluation/feedback/holdout_v0.10.result.json": "82b02f2ca337274c4cbd0faa665615e90b5b8ce9e16d53a76949ba493b04e595",
    "evaluation/feedback/holdout_v0.11.jsonl": "a020895a9b289fd5e4a1b68660486898d4813b5b72d542da89855df8e745b984",
    "evaluation/feedback/holdout_v0.11.manifest.json": "0f28a1a698e00f1faf0187c582fbaec35ff345b2cfd56755a6350bf1895d4df0",
    "evaluation/feedback/holdout_v0.11.protocol.json": "f439f8d7c7bf839fa807c48642916c14c4bd2fcc21b1389b47c3f3bf5ab60b06",
    "evaluation/feedback/build_holdout_v0_11.py": "7e1370dfed820999a207efeeeb5f1ea1c3938911c3e55addc758418a5d21bab9",
    "training/feedback/HOLDOUT_V0.11_SEAL.md": "32fc4b199fa010b4ce2378abe2391b595d0e0b3969a8ea82199cdcb27b34213b",
    "training/feedback/config_v0.6.json": "1ba63da7578f3f9a2fb4ab8e28cee863dc627a9e614dfef5a4d43e3d6687734d",
    "training/feedback/data/feedback_v0.6.two-stage.jsonl": "39eda98851cb42c5bd608d48f794d020a4d80214cd827c7e5e78ac99fa8e5dfe",
    "training/feedback/data/train_v0.6.two-stage.chatml.jsonl": "3a2864966bf37ba9e30557711d4caa0438dc90e7ed7f22be895979685eec63b8",
    "training/feedback/data/eval_v0.6.two-stage.chatml.jsonl": "6bc814bf7ccc5b80ace88a51bb330236aa9d167301840fa499baae06a67cde10",
    "training/feedback/data/feedback_v0.6.two-stage.manifest.json": "80d05ae2f9ba9e7930e3d55c363443cdf576364f97f71cc6614443006563c331",
    "training/feedback/config_v0.7.json": "f5a3534e6d996db6a7a34cdbe181f9dc813bcb64f96616812c260989fa9f8d7f",
    "training/feedback/data/feedback_v0.7.stage1-comparison.jsonl": "e3cd954b3b0379f233af3300861a843f98e7f9c5ece67317bd2643fe765b2fda",
    "training/feedback/data/train_v0.7.stage1-comparison.chatml.jsonl": "5d9ddc9b03a3b1c7aec3b85e268ef0aebca0653fcd773779680f85dff66c982b",
    "training/feedback/data/eval_v0.7.stage1-comparison.chatml.jsonl": "8590e228330b14778c5c515b485b7a7d38ec787826c1ec61ef1f71671ff4923b",
    "training/feedback/data/feedback_v0.7.stage1-comparison.manifest.json": "6bee8f55136dd15b40faa986ab8e2bbb02eee8d56ee6a4981bd4db7abf594b1c",
    "training/feedback/config_v0.8.json": "b8fd543fbffe80dfa8a3fb2bbfbea417822ada14db7ec3f1ad64c9e9d9959e6a",
    "training/feedback/data/feedback_v0.8.stage2-recovery-style.jsonl": "07ae62567c5448066b107bd07b96372c65548146a7c3c542cc6cec542090ab6d",
    "training/feedback/data/train_v0.8.stage2-recovery-style.chatml.jsonl": "71cabbdc57fd791a946797553339bdbe4dcf758a06d506deeddfbb18ba5cbc49",
    "training/feedback/data/eval_v0.8.stage2-recovery-style.chatml.jsonl": "0efe383190ad578c4b5b7eb301dad41eeec1201899730667341bb5f197a63a52",
    "training/feedback/data/feedback_v0.8.stage2-recovery-style.manifest.json": "a8a95034da970e9aa37450f9f4756627a51423568952a12a97544ca40bbc634b",
    "evaluation/feedback/holdout_v0.11.execution-plan.json": "6d2d776cedbeffb27b2039a78a2905423a9d4449eb6c93842b89e79eded3c83d",
    "evaluation/feedback/holdout_v0.11.execution-record.json": "86f2754dc49134d484dfd1b7a44ec6749c11a08adf5d9a81c8a895cb60a27a4f",
    "evaluation/feedback/holdout_v0.11.result.json": "25ee4ca9e3652fba0681ee51c21864b9fc9a4a3c9b34f88d5edfbfec2f39aa5d",
    "training/feedback/config_v0.9.json": "4489b04dcf43fe0b8a73dd85b7f2175252d4defa2b9c2e9261cd24b9088787de",
    "training/feedback/data/feedback_v0.9.stage2-contract-stability.jsonl": "c717cce5637e627b805d92b842f56b03e1de76ff6300efd5cb954fed4aabd174",
    "training/feedback/data/train_v0.9.stage2-contract-stability.chatml.jsonl": "e328e41bd3d082e0da492f7a50b95b043aed1095cfdbc048ff9122d5e64fda12",
    "training/feedback/data/eval_v0.9.stage2-contract-stability.chatml.jsonl": "96036bdbbeca272c91ec450ca859207c3d964d8fd21717db31a79f7751a517fd",
    "training/feedback/data/feedback_v0.9.stage2-contract-stability.manifest.json": "fa8c848418d52748cf853361c22a1c9122db0273543c904dd0b1f2f9b8c692ae",
    "training/feedback/generate_v0_9_stage2_contract_stability.py": "13f81a9e4568d952a82955bb9f6ddeb5dd0e7cd3a4272e3089e36e68284d2cb8",
    "training/feedback/FEEDBACK_V0.9_HOLDOUT_V0.11_RESULT.md": "6087cc0ffcfb663bf6d6f4a097b4ad706af390d8150322d0b7923546ea2cc294",
    "analyzer/feedback_two_stage_contract.py": "d9e5e4d1c7faa4a032f9f0b5073552f088f34dab00083be31160b5062ce20e68",
    "analyzer/feedback_service.py": "e5314e810d044080976aa2136257b45050903b56cc758f173722fbdc43ef0a45",
    "analyzer/feedback_store.py": "1ca9f27cb9b8199fdb64d4cd2d86ead2d33f2af5eb62118c4c0fd8230629f081",
    "analyzer/feedback_worker.py": "6d64467a914308d8d58201cf6d8be888d1f7ba07a5859db375396859d9ed6981",
    "deployment/feedback-staging/feedback-staging.env.example": "772233eb2a880fe5d5d61fba84a8e4545b833cafc6dabf17b749c5f9b91c9dc3",
    "deployment/feedback-staging/feedback-vllm.service": "86c00479d0ad0395d5b154d7407c2d9b268fc10a0ea792c3f00b097fccef08d9",
    "scripts/diagnose_feedback_failed_stages.py": "6a3268a9c024caaca04e2e0094d82c44e7e25281b2684c77954319633fb89659",
    "scripts/validate_feedback_model_policy.py": "bc545fed9bb677a3b71b0142ef9006f94e64a25a34d2c82c8c873be1b0ce3aab",
    "evaluation/feedback/two_stage_runner.py": "d11efec2d5f370570f2fb4299227e851c759326db9e09ad94283f4f1190fc3af",
    "evaluation/feedback/two_stage_scorer.py": "845fd2706984e357f11c2e954a23246bbfa6d96ca3cb6c5febd57d6856fc4bda",
}
EXTERNAL_HASHES = {
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.9-stage2-contract-stability/adapter_model.safetensors": "ce68df0d09446bea943e5b800995cd489703bce7a2f57544f974cc3b069f4cdc",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.9-stage2-contract-stability/run_manifest.json": "ca0708946b2df8fb9fa352a24549c04f9dfb6a471e78b5aa221f1ee5b5ad074a",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.11-v09.jsonl": "5681e535aaea04ef672ad1d48c7fffef4048ffdd5aeff0ae74168cc8035e35b8",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.11-v09.jsonl.manifest.json": "d8f017e5cf969a2786b4e41b63bc4a901c65f0f64e33b8107d3acea8210421a1",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.11-v09.claim.json": "73bbd72ee0e728a6552c408307817235a718c02351ad3dfdaffa8a9764b0dad7",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.11-v09.receipt.json": "8087b8d95d1cb344ff8050517b5cb15458bfa9e454b8ff75f034b5a34e6c055e",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.8/actual-shadow-v0.1.failure-stage-diagnostic.json": "084c00c0533cdc54c0b988b45fe02cb2f3a17db2a4dd610ef9cb4657a8771fa1",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.8-v06.jsonl": "570f0be17298befe5e08755437c60f242643570e952d25aa735775e75873b759",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.8-v06.jsonl.manifest.json": "18e9a597239c13060dd3ed32625029a1849d37ca10ff6928541ed90b71e83d70",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.8-v06.claim.json": "dc187aa347a443404df09b0dfdf2e1ffb5c26c687af0e7ec406512d0019237d1",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.8-v06.receipt.json": "b228e9c3cf0fb5de4d817b45e276586997ae3a9aba448ec6ea2818b2b547a36f",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.6-two-stage/adapter_model.safetensors": "7095ba9aba1cc1a94ee3558e92c485758498c8cfe05f792f58fcc738c5ec4475",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.6-two-stage/adapter_config.json": "2f45673a89a3500b5ec94867ad6e6d5535e2306371d6580e51a869333a77fad9",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.6-two-stage/run_manifest.json": "7e7e15bd87f31ad8d5fa9b99df8bb242e6c84caea3670c2c0b10baf97f95a6cf",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.7-stage1-comparison/adapter_model.safetensors": "d336e68a82643a9e161f6430ffb7f7fc164c6dd3ac9e863891b82564e9444382",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.7-stage1-comparison/adapter_config.json": "4f838052826b24e2cad6181a8a90565198f68ba8722b868ea61b73f4164da974",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.7-stage1-comparison/run_manifest.json": "5a29a922628252596d862b5a80e07f166df6ae450aaef75a1def7199d7646b82",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.8-stage2-recovery-style/adapter_model.safetensors": "c2f5901f97474337617f8e81fa61257f5e5d556f8b61a19ab57cb3e5e91e6180",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.8-stage2-recovery-style/adapter_config.json": "33cdee4522aff5293c2263d55a903597fb6b32e0401d43918742d4d5f32abb87",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.8-stage2-recovery-style/run_manifest.json": "99445e0f031ebd960f9463113bcb66ccfbbfea2c05a969a41f95d79900da96e9",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.10-v08.jsonl": "6109d39728cebd13081f351f76e0f804302bb33eb9d1af1b52c6c5a953275892",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.10-v08.jsonl.manifest.json": "5d29f5d9da4cc4f53d24ed5fa446d2b711d3f1316e91934af36c9dec50e72ef4",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.10-v08.claim.json": "1e6ab4b373221ed83ef32764dbfd9c1418558189591ab5fd03872ff8f63c4ff5",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.10-v08.receipt.json": "25e3fb051bc9e5d5969b1cdc0160fa05f460df0cd9c3a415127eaff196a2d88a",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.9-v07.jsonl": "a0e19c0b3d7127212df1e2ed1489233236d166d5fb9bce18f05002b89c9ed60c",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.9-v07.jsonl.manifest.json": "2e70d08d271a29352d3596fb3d5bc6f9ae0a603dd7467d8f3e8b43171a3ef00c",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.9-v07.claim.json": "9d3e7b0b0292ffcd7f71a89fd9a117eb83007d4f3c283bc6e3339e34bea9f641",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.9-v07.receipt.json": "61ade50dcea2dbbad114c821a7d10f2786b5791b5708024e641a49f0caceb91f",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.7-v05.jsonl": "d8550bb0fa5e32ccc7b1245e8155e1f1bf55d6ceed95722f3dd40d4be4c9289f",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.7-v05.jsonl.manifest.json": "0b1c51eeeb97844e0eac192b453aefd7af927a39b3629b028eb0ad9027e4138c",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.7-v05.claim.json": "3bceea7c7a973bdc831c9bc014db563e632023809131af2c661a469e64f41103",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-two-stage-v0.1/holdout-v0.7-v05.receipt.json": "f6c235fd40824298c711c1d3607f685be1a91e98424885a49260e43557d64106",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.5/adapter_model.safetensors": "f6896ab2f0fdd408fb42a4a1fa6fa28f5039f557fab25a0aa7b7a1e76af52d95",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.5/adapter_config.json": "2124306d7a848b078aff0ac5e4355e64588a904b271e4c4d95c65c0540aff1c7",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.5/run_manifest.json": "be5a802a6127d9804f3162327410aaf6cef8fbd43ef3455ba8dded9e29f80e2f",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-base.jsonl": "eab86a8b624b37022f47e339473883842351820c4ad99dccfebdcd3b7cff73ec",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-base.jsonl.manifest.json": "37fe7cc9557c63f36aa489d91f7fdbd087c22696d7de37b5d99bc71e1083549d",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-base.score.json": "6ae951d53e281ebf75913abf5da314df4186abcf75a9248a1da7cad062324e44",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-lora.jsonl": "b8af7b90cd69e1d452463f8cfeacbdc9df428cd1d80bac0e30f048cc00dd9a61",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-lora.jsonl.manifest.json": "6ad82446cf68bb4cf9efd2cd6e77ce94a8fa015d661cf18d0e9740d3c52e4aa4",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.5/holdout-v0.6-lora.score.json": "1c95b0df858aa65bedcb379a07accbdc6e601f71c658a6ae60b8158ba6c619af",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.4/adapter_model.safetensors": "2af21a821c1f3ad816fc28035479d3525f7aa22eac70c028b1e8a752cdebc78a",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.4/adapter_config.json": "4f2279d22200ba5d64990982f0ce5361f825acbf4d4059526aa8ffad55889765",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.4/run_manifest.json": "62f7ac5bd0863ca77e5b9b681835d65f6f3a812833de184b9f4ee7d087290d09",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-base.jsonl": "6de71acdd4564c2066210677e58482ca2fb134e455a6b2fab4864e260606165e",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-base.jsonl.manifest.json": "c88021138ecdc3ed02873d8656fad920dd81693553ade40b3fbc989958e78062",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-base.score.json": "26c1ac0558be039c5ccbdf65cff98054ca68e68143fac89398d640f7781355f5",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-lora.jsonl": "57851676e541b0daddcf474e1465a589ffe51189a0f23613506bf2b1d3303219",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-lora.jsonl.manifest.json": "1a274cf7b97784872ff02de1824ea3bbbd190c9a7a77d7518cd9bffbab61b33b",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.4/holdout-v0.5-lora.score.json": "42c0fbb23553de942860de797918adf4ebf7f0967d53f7afba3a7eacd3e2bcef",
    "/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.3/adapter_model.safetensors": "3bcbc80d1559dacf60a84c708a8ab4c51ee4bd33532acf2ab134394aa2dcd1ad",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/holdout-v0.4.jsonl": "6d3fe9032251403e05d2c8ab970ee7bd7f1ddb11c6f9c5d2afa9e1aeab4abf32",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/holdout-v0.4-base-retrospective.jsonl": "c2951a96421ca24db5a20d81d93b4aee59184eb70e6dc7988b344ab3d243be1c",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/holdout-v0.4-base-retrospective.jsonl.manifest.json": "c7f15b8aa04cdfb8823358b97660b16c954508f8f66deaf2dc4657b00f4cf0ea",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/holdout-v0.4-base-retrospective.score.json": "6183984dee6dcddb424a6a1b5c6edc354c39decc5363f8bfe0086aeba4db59be",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.jsonl": "49fcbbb59fcbec53e1ec0014220e411aab58bf72e8de0452c45a4e27f5acfb95",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.jsonl.manifest.json": "798d6b85f3bb4cee95bf5921a15b1e9cfad2cdac8b6a31198f3ed2aecaab99cb",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.score.json": "12e00f5d778513fa105b0fec37d8640e04c694ab5cd5b895514c15c4ea32e4f6",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.hardened.jsonl": "cab9fb7c6ec2dd00712dd508936a957555fa2ac9d10616794fb5fff5b3c02072",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.hardened.jsonl.manifest.json": "e1a485eb8caee607a1281027c030994a58265c179d933ff0628b63c7d27fe5d4",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.1.hardened.score.json": "a5aeeb6bff62d587c227712aad9b980b45ba4d833b6892f5123da199fab447a0",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/synthetic-shadow-v0.1/judgment.jsonl": "d2a581992f4efb1a7129883a5c220dac3d7e69bdab8728c565e53fe5c296106c",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/synthetic-shadow-v0.1.sqlite3": "e3f6e1090fbf8b29927647344adad2e143e07576aced7c26daf8f5e25d5f7ec1",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/actual-shadow-v0.1.inputs.jsonl": "667b0b3c6a074ac9e9a1f46e5a520408dd367f2c79becfe1a7d53b08e9de1330",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/actual-shadow-v0.1/judgment.jsonl": "cfea98563a13bd8d9e11c8797a6217b04eb8b89e2e4b042b437a76bfe6cf1e16",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/actual-shadow-v0.1.sqlite3": "988f21db29cd5c3720f879e378e99386649ad198b4b387f2a5b40db9360f29db",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.2.jsonl": "6317612d05720d5d6de25ec8febf862571156fbfd2e75a09ef7bd4eed90c012a",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.2.jsonl.manifest.json": "1c9996e96bfbb2b8d9ed15cfdade8ae045f474545a79600b025ec371383518f4",
    "/home/cap-minsung/lora-adapter-bank/runs/feedback-v0.3/existence-particle-diagnostic-v0.2.score.json": "1ecc9e77cb2d96aa689ecd2a239c0d7287b3e5b8019a42ae5441e58132e6b897",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "huggingface_token": re.compile(r"hf_[A-Za-z0-9]{20,}"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True,
    ).stdout


def changed_paths(root: Path) -> list[str]:
    values = git_output(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries = values.decode("utf-8").split("\0")
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]; index += 1
        if not entry:
            continue
        paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            paths.append(entries[index]); index += 1
    return sorted(set(paths))


def is_checkpoint(path: str) -> bool:
    return path in CHECKPOINT_ROOT_FILES or any(path.startswith(prefix) for prefix in CHECKPOINT_PREFIXES)


def prohibited_reason(path: str) -> str | None:
    return next((pattern for pattern in PROHIBITED if fnmatch.fnmatch(path, pattern)), None)


def verify_hashes(values: dict[str, str], *, root: Path | None = None) -> dict[str, dict[str, Any]]:
    result = {}
    for name, expected in values.items():
        path = (root / name) if root is not None else Path(name)
        actual = sha256_file(path) if path.is_file() else None
        result[name] = {"expected": expected, "actual": actual, "matches": actual == expected}
    return result


def audit(root: Path = ROOT, *, require_external: bool = True) -> dict[str, Any]:
    root = root.resolve()
    changed = changed_paths(root)
    deferred = sorted(path for path in changed if path in DEFERRED_PI_PATHS)
    checkpoint = sorted(path for path in changed if path not in DEFERRED_PI_PATHS and is_checkpoint(path))
    unknown = sorted(set(changed) - set(deferred) - set(checkpoint))
    staged = [value for value in git_output(root, "diff", "--cached", "--name-only")
              .decode("utf-8").splitlines() if value]
    prohibited = {path: prohibited_reason(path) for path in checkpoint if prohibited_reason(path)}
    oversized = {
        path: (root / path).stat().st_size for path in checkpoint
        if (root / path).is_file() and (root / path).stat().st_size > MAX_BYTES
    }
    secrets: dict[str, list[str]] = {}
    for path in checkpoint:
        absolute = root / path
        if not absolute.is_file():
            continue
        text = absolute.read_text(encoding="utf-8", errors="ignore")
        matches = [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]
        if matches:
            secrets[path] = matches
    internal_hashes = verify_hashes(KEY_HASHES, root=root)
    external_hashes = verify_hashes(EXTERNAL_HASHES)
    ignored_checks = {}
    for path in (
        "evaluation/feedback/runs/example.jsonl",
        "evaluation/feedback/intake/example.jsonl",
        "example.safetensors", "example.sqlite3",
    ):
        code = subprocess.run(["git", "check-ignore", "--quiet", "--no-index", path], cwd=root).returncode
        ignored_checks[path] = code == 0

    errors = []
    if unknown: errors.append("unclassified changed paths")
    if staged: errors.append("files are already staged")
    if prohibited: errors.append("prohibited checkpoint paths")
    if oversized: errors.append("checkpoint files exceed 10 MiB")
    if secrets: errors.append("secret-like token patterns found")
    if not all(item["matches"] for item in internal_hashes.values()): errors.append("internal hash mismatch")
    if require_external and not all(item["matches"] for item in external_hashes.values()): errors.append("external hash mismatch")
    if not all(ignored_checks.values()): errors.append("private artifact ignore rule missing")
    return {
        "schema_version": "feedback-v0.3-checkpoint-audit-v0.1",
        "passed": not errors, "errors": errors,
        "changed_path_count": len(changed),
        "checkpoint_path_count": len(checkpoint),
        "deferred_pi_path_count": len(deferred),
        "checkpoint_paths": checkpoint, "deferred_pi_paths": deferred,
        "unknown_paths": unknown, "staged_paths": staged,
        "prohibited_checkpoint_paths": prohibited,
        "oversized_checkpoint_files": oversized,
        "secret_pattern_matches": secrets,
        "internal_hashes": internal_hashes,
        "external_hashes": external_hashes,
        "external_hashes_required": require_external,
        "private_artifact_ignore_rules": ignored_checks,
        "content_scanned_for_secret_patterns": True,
        "mutations_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.root)
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
