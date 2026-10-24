"""The ML force fields under test and how kUPS loads each one."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    developer: str
    training_data: str
    license: str
    backend: str  # "tojax" (CuspAI JAX export), "uma" (kUPS PyTorch bridge, GPU only) or "ase-<name>" (official package)
    model_path: str
    extra: dict = field(default_factory=dict)
    gated: bool = False
    color: str = "#888888"
    via_kups: bool = True
    excluded: str | None = None  # set when a model's results must not be used, with the reason

    def potential_config(self, device: str = "cpu"):
        """Return the kUPS potential config object for this model."""
        from kups.application.simulations.potentials import TojaxPotentialConfig, UmaConfig

        if self.backend == "tojax":
            return TojaxPotentialConfig(model_path=self.model_path)
        if self.backend == "uma":
            return UmaConfig(model_path=self.model_path, device=device, **self.extra)
        raise ValueError(f"unknown backend {self.backend!r}")


MODELS: dict[str, ModelSpec] = {
    m.key: m
    for m in [
        ModelSpec(
            key="mace-mpa-0",
            label="MACE-MPA-0 (medium)",
            developer="MACE team (Cambridge et al.)",
            training_data="MPtrj + sAlex subset of Alexandria (PBE/PBE+U)",
            license="MIT",
            backend="tojax",
            model_path="hf://CuspAI/kUPS-mace-jax/mace-mpa-0-medium_32.zip",
            color="#2a78d6",
        ),
        ModelSpec(
            key="orb-v3",
            label="Orb v3 (conservative, OMat)",
            developer="Orbital Materials",
            training_data="OMat24 (PBE/PBE+U, VASP 54 PAWs)",
            license="Apache-2.0",
            backend="tojax",
            model_path="hf://CuspAI/kUPS-orb-jax/orb_v3_conservative_inf_omat.zip",
            color="#eb6834",
        ),
        ModelSpec(
            key="mattersim-5m",
            label="MatterSim v1 (5M)",
            developer="Microsoft Research",
            training_data="MatterSim's own sampled PBE/PBE+U dataset",
            license="MIT",
            backend="tojax",
            model_path="hf://CuspAI/kUPS-mattersim-jax/mattersim-v1.0.0-5m.zip",
            color="#1baf7a",
            excluded=("the kUPS JAX export returns energies that depend on neighbour-list order and supercell "
                      "size (scripts/repro_mattersim_export.py); MatterSim is benchmarked through its official "
                      "package instead (mattersim-5m-native)"),
        ),
        ModelSpec(
            key="mattersim-5m-native",
            label="MatterSim v1 (5M), official package",
            developer="Microsoft Research",
            training_data="MatterSim's own sampled PBE/PBE+U dataset",
            license="MIT",
            backend="ase-mattersim",
            model_path="MatterSim-v1.0.0-5M.pth",
            color="#1baf7a",
            via_kups=False,
        ),
        ModelSpec(
            key="uma-s-1p2",
            label="UMA small 1.2 (omat task), official package",
            developer="Meta FAIR",
            training_data="OMat24 (+ other Meta datasets; omat head used)",
            license="FAIR Chemistry License (gated on Hugging Face)",
            # kUPS's PyTorch bridge needs a GPU, so on CPU UMA runs through fairchem's own calculator
            backend="ase-uma",
            model_path="hf://facebook/UMA/checkpoints/uma-s-1p2.pt",
            extra={"name": "uma-s-1p2", "task_name": "omat", "inference_settings": "default"},
            gated=True,
            color="#eda100",
            via_kups=False,
        ),
    ]
}


def get_model(key: str) -> ModelSpec:
    try:
        return MODELS[key]
    except KeyError:
        raise KeyError(f"unknown model {key!r}; choose from {sorted(MODELS)}") from None
