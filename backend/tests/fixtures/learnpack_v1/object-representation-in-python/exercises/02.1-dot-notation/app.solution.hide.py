class User:
    def __init__(self, username, bio):
        self.username = username
        self.bio = bio

    def update_bio(self, new_bio):
        self.bio = new_bio


user = User("jane_doe", "Traveler and photographer")
print(user.username)  # Outputs: jane_doe
print(user.bio)  # Outputs: Traveler and photographer

user.update_bio("Loves photography")
print(user.bio)  # Outputs: Loves photography

user.bio = "Photographer and blogger"
print(user.bio)  # Outputs: Photographer and blogger
