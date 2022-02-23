from collections import OrderedDict as _OrderedDict


class _charge_table(_OrderedDict):
    """Small wrapper around OrderedDict that returns the value
    associated with the largest key smaller than the requested
    key value."""

    def __init__(self, *args, **kwargs):
        if len(args) > 0 and isinstance(args[0], dict):
            args = list(args)
            try:
                args[0] = [(float(k), v) for k, v in args[0].items()]
            except ValueError:
                raise ValueError(f"Charge table keys must be numeric")
            args[0].sort(reverse=True)
            super().__init__(*args, **kwargs)

    def __getitem__(self, value):
        try:
            float(value)
        except ValueError:
            raise ValueError(f"Charge table keys must be numeric")
        for key in self.keys():
            if float(value) >= key:
                return super().__getitem__(key)
        raise ValueError(f"Value '{value}' does not exist in defined ranges")


def cpu_2022(ad):
    cpu_charge_table = _charge_table(
        {
            0: 1.0,
            2: 1.2,
            9: 1.5,
            33: 2.0,
        }
    )

    memory_charge_table = _charge_table(
        {
            0: 0,
            0.001: 0.125,
            8.001: 0.250,
            32.001: 0.375,
            128.001: 0.50,
        }
    )

    cpu_hyperthread_discount = 0.4
    nominal_memory_gb_per_cpu = 2

    cpus = ad.get("RequestCpus", 1)
    cpu_hyperthread = ad.get("IsHyperthreadCpu", False)
    memory_gb = ad.get("RequestMemory", 0) / 1000
    hours = ad.get("RemoteWallClockTime", 0) / 3600

    above_nominal_memory_gb = max(memory_gb - (cpus * nominal_memory_gb_per_cpu), 0)

    charge = hours * (
        cpu_charge_table[cpus]
        - cpu_charge_table[cpus] * (cpu_hyperthread * cpu_hyperthread_discount)
        + memory_charge_table[above_nominal_memory_gb]
    )

    return charge


def gpu_2022(ad):
    gpu_charge_table = _charge_table(
        {
            0: 0,
            1: 1.0,
            2: 1.2,
            3: 1.5,
            4: 2.0,
        }
    )
    cpu_charge_table = _charge_table(
        {
            0: 0,
            1: 0.125,
            49: 0.20,
        }
    )
    memory_charge_table = _charge_table(
        {
            0: 0,
            0.001: 0.012,
            384.001: 0.20,
        }
    )

    cpu_hyperthread_discount = 0.4
    nominal_cpus_per_gpu = 16
    nominal_memory_gb_per_gpu = 2

    gpus = ad.get("RequestGpus", 0)
    cpus = ad.get("RequestCpus", 1)
    memory_gb = ad.get("RequestMemory", 0) / 1000
    hours = ad.get("RemoteWallClockTime", 0) / 3600

    above_nominal_cpus_per_gpu = max((cpus - 16 * gpus) / gpus, 0)
    above_nominal_memory_gb_per_gpu = max((memory_gb - 128 * gpus) / gpus, 0)

    charge = hours * (
        gpu_charge_table[gpus]
        + cpu_charge_table[above_nominal_cpus_per_gpu]
        + memory_charge_table[above_nominal_memory_gb_per_gpu]
    )

    return charge
