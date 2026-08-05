class Warrior:
    def __init__(self, name, health):
        self.name = name
        self.health = health

    def take_damage(self, amount):
        self.health = self.health - amount

    # TODO: Add a heal method that increases health by a given amount


# Create two warriors
warrior1 = Warrior("Leon", 100)
warrior2 = Warrior("Max", 100)

# TODO: Call take_damage on warrior1 with 30 damage

# TODO: Call heal on warrior2 with 20 health

# TODO: Print the name and health of both warriors
