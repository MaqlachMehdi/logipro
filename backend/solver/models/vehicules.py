from dataclasses import dataclass

@dataclass
class Vehicle:
    id:         str
    max_volume: float

    def __post_init__(self):
        if self.max_volume <= 0:
            raise ValueError(
                f"Vehicle {self.id} has non-positive volume ({self.max_volume} m³)"
            )

    def __str__(self):
        return f"Vehicle: {self.id} (max {self.max_volume} m³)"