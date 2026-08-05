class Warrior:
    def __init__(self, name, health):
        self.name = name
        self.health = health


warrior1 = Warrior("Aragorn", 100)
warrior2 = Warrior("Legolas", 90)

print(warrior1.name)  # Output: Aragorn
print(warrior2.health)  # Output: 90
