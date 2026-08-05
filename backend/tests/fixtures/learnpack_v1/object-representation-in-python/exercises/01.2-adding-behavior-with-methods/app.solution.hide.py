class Warrior:
    def __init__(self, name, health):
        self.name = name
        self.health = health

    def take_damage(self, amount):
        self.health -= amount

    def heal(self, amount):
        self.health += amount


# Create two warriors
warrior1 = Warrior("Leon", 100)
warrior2 = Warrior("Max", 100)

# Call take_damage on warrior1 with 30 damage
warrior1.take_damage(30)

# Call heal on warrior2 with 20 health
warrior2.heal(20)

# Print the name and health of both warriors
print(f"{warrior1.name} has {warrior1.health} health.")
print(f"{warrior2.name} has {warrior2.health} health.")
