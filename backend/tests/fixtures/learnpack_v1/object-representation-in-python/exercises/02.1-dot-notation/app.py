class User:
    def __init__(self, username, bio):
        self.user = username
        self.bio = bio

    def update_bio(self, new_bio):
        self.bio = new_bio


user = User("jane_doe", "Traveler and photographer")
# print object attributes

user.update_bio("Loves photography")
# print object attributes

user.bio = "Photographer and blogger"
# print object attributes
