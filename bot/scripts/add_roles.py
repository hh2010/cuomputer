from datetime import datetime, timezone

import discord
from firebase_admin import firestore
from rich import print

import config

# from bot.db.fbdb import db
from bot.db.fbdb import get_firestore_db
from bot.db.fetch_data import fetch_users
from bot.scripts.get_firestore_user import get_firestore_user
from bot.scripts.message.fix_nick import fix_nick

# from bot.setup.init import firestore_users, client
from bot.setup.discord_bot import client

# from config import (
#     # bundles_map,
#     # time_based_roles,
#     # firestore_time_format,
#     # og_cutoff,
#     # user_to_remove,
#     # GUILD_ID,
#     members_to_skip,
# )



async def add_time_based_roles(member, roles):
    """
    If you want to change the name of the role, replace all in discord_bot
    and don't forget to change the name of the role in server/roles/settings.

    0.2: "Visitor",
    0.4: "Friend",

    2: "Neighbor",
    """
    print('add_time_based_roles')

    now = datetime.now(timezone.utc)
    joined_at = member.joined_at
    delta = now - joined_at
    # print(delta)
    # days = delta.days
    hours = int(delta.total_seconds() / 3600)
    # print(member.name, delta, "; hours: ", hours)
    # if hours < 1000:
    # print(f"add_time_based_roles for {member.name} who joined {hours} hours ago.")

    member_roles = [x.name for x in member.roles]
    # print(member_roles)
    # print(time_based_roles)

    if hours >= config.neighbor_role_waiting_period:
        if "Visitor" in member_roles:
            print(f"Removing Visitor from {member.name}")
            role = next((x for x in roles if x.name == "Visitor"), None)
            # print(role)
            await member.remove_roles(role)
        if "Neighbor" not in member_roles:
            print(f"Adding Neighbor to {member.name}")
            role = next((x for x in roles if x.name == "Neighbor"), None)
            # print(role)
            await member.add_roles(role)
    else:
        if "Visitor" not in member_roles:
            print(f"Adding Visitor to {member.name}")
            role = next((x for x in roles if x.name == "Visitor"), None)
            # print(role)
            await member.add_roles(role)
        """ YOU CAN'T REMOVE NEIGHBOR AUTOMATICALLY CUZ SOME NEWBIES MAY HAVE A BUNDLE """
        # if "Neighbor" in member_roles:
        #     print(f"Removing Neighbor from {member.name}")
        #     role = next((x for x in roles if x.name == "Neighbor"), None)
        #     # print(role)
        #     await member.remove_roles(role)

    # # k, v
    # for threshold, role_name in time_based_roles.items():
    #     # print(threshold, role_name)

    #     role = None

    #     # Remove Visitor role so it can give exclusive access to newbies in Welcome
    #     if role_name == "Visitor":
    #         # print("Visitor")

    #         if "Visitor" in member_roles and "Neighbor" in member_roles:
    #             print(f"Removing Visitor from {member.name}")
    #             role = next((x for x in roles if x.name == role_name), None)
    #             # print(role)
    #             await member.remove_roles(role)
    #             # print(member.roles)
    #         continue

        # elif hours >= threshold:
        #     # print(f"Not Visitor so going on to check {role_name}")
        #     # print(hours, threshold, role_name)

        #     # Create the role object
        #     role = next((x for x in roles if x.name == role_name), None)
        #     # print(role)

        #     if role not in member.roles:

        #         # print(hours, " >= ", threshold, " == ", hours > threshold, end=" so ")
        #         print("adding role ", role_name, f" for {member.name}")

        #         # add the role object to the member
        #         await member.add_roles(role)

        # """ YOU CAN'T REMOVE NEIGHBOR AUTOMATICALLY CUZ SOME NEWBIES MAY HAVE A BUNDLE """
        # else:
        #     # member_roles = [x.name for x in member.roles]
        #     if role in member.roles:
        #         print(
        #             days,
        #             " < ",
        #             threshold,
        #             " == ",
        #             days > threshold,
        #             end=f" so removing {role.name} for {member.name}",
        #         )

        #         await member.remove_roles(role)
        # print("\n")


async def add_remove_roles_for_specific_users(author, roles):
    print("add_remove_roles_for_specific_users")
    if author.id == config.user_to_remove:
        await author.remove_roles(next(x for x in roles if x.name == "Camp Counselor"))
        await author.remove_roles(next(x for x in roles if x.name == "Archivist"))
        await author.remove_roles(next(x for x in roles if x.name == "Librarian"))


def get_firestore_user_by_id(member_id):
    """
    Directly queries Firestore for a single user by Discord ID.
    
    This is more efficient than fetching all users when we only need one.
    
    Parameters:
    member_id (int): The Discord ID to query for
    
    Returns:
    dict: The user data if found, None otherwise
    """
    print(f"Querying Firestore directly for user with Discord ID: {member_id}")
    
    # Convert to string for Firestore query
    discord_id = str(member_id)
    
    db = get_firestore_db()
    users = db.collection("users").where("discordId", "==", discord_id).limit(1).get()
    
    if not users or len(users) == 0:
        return None
    
    # Convert Firestore document to dict and standardize fields
    user_dict = users[0].to_dict()
    user_dict["id"] = users[0].id
    return standardize_firestore_user(user_dict)


def standardize_firestore_user(user):
    """
    Standardizes a Firestore user dictionary by ensuring all expected fields exist
    with default values if they're missing.
    
    Parameters:
    user (dict): The original user dictionary from Firestore
    
    Returns:
    dict: A standardized user dictionary with all expected fields
    """
    # List of roles that contribute to the user's score
    roles_for_score = [
        'Manager', 'boss', 'Archivist', 'Tour Guide', 'Librarian', 'Translator',
        'Curator', 'Promoter', 'Parental Advisory', 'Graphic Design', 'Data Scientist',
        'Welcome Committee', 'Creative Director', 'Discordian', 'Broadway Producer',
        'Weezler', 'Assistant Engineer', 'Recording Engineer', 'Show Producer', 'iPhone',
        'Android', 'Stage Manager', 'Casting Director', 'tik-tok', 'Biographical Researcher',
        'Cameraman', 'Night Watchman', 'Champion', 'Supporter', '1000+', '400+', '100+',
        'Setlist Expert', 'Eagle Brain', 'Eagle Eyes', 'Eagle Ears', 'Camp Counselor',
    ]
    
    # Build a score based on badges and bundles
    def build_score(user_data):
        score = 0
        if "badges" in user_data and user_data["badges"]:
            service_badges = [x for x in user_data["badges"] if x in roles_for_score]
            score = len(service_badges)
        if "bundleIds" in user_data and user_data["bundleIds"]:
            score += len(user_data["bundleIds"])
        return score
    
    # Create standardized user with default values
    standardized_user = {
        "id": user["id"] if "id" in user else "",
        "discordId": user["discordId"].strip() if "discordId" in user else "",
        "bundleIds": user["bundleIds"] if "bundleIds" in user else [],
        "badges": user["badges"] if "badges" in user and user["badges"] else [],
        "banned": user["banned"] if "banned" in user else False,
        "email": user["email"] if "email" in user else "",
        "lastSeen": user["lastSeen"] if "lastSeen" in user else None,
        "profileImageUrl": user["profileImageUrl"] if "profileImageUrl" in user else "",
        "registeredOn": user["registeredOn"] if "registeredOn" in user else None,
        "username": user["username"] if "username" in user else "",
        "discordConnected": user["discordConnected"] if "discordConnected" in user else False,
    }
    
    # Calculate and add score
    standardized_user["score"] = build_score(user) if "score" not in user else user["score"]
    
    return standardized_user


async def check_firestore_and_add_roles_and_nick(member, roles):
    """
    Assigns roles and nicknames based on Weezify account connection status.
    
    This function is crucial in the Discord-Weezify integration:
    1. Checks if a Discord member has a connected Weezify account
    2. If connected, assigns appropriate roles based on:
       - Registration date (OG status)
       - Purchased bundles (bundle-specific roles)
       - Badges earned in Weezify
    3. Sets the user's Discord nickname to match their Weezify username
    
    Role Assignment Flow:
    1. Retrieve the user's Firestore record directly by Discord ID
    2. If found, assign roles based on Weezify data
    3. If not found, fix their nickname and return None for firestore_user
    
    Known Issues:
    - Users who receive the Neighbor role before connecting can enter a "limbo" state
    - Some role assignments depend on time-based conditions
    
    Parameters:
    member (Member): The Discord member object
    roles (list): List of available roles in the Discord server
    
    Returns:
    tuple: (member, nickname, firestore_user) where:
           - member is the updated member object
           - nickname is the user's new nickname
           - firestore_user is the user's data from Firestore or None if not connected
    """
    print('check_firestore_and_add_roles_and_nick')
    
    # Get user directly from Firestore instead of the cached list of all users
    firestore_user = get_firestore_user_by_id(member.id)

    # ROUTINES TO RUN ON FIRESTORE USERS
    if firestore_user is not None:
        # print(firestore_user)

        nick = firestore_user["username"]

        if member.id != config.cuomputer_id:

            await add_og_role_from_firestore_user(member, firestore_user, roles)

            await add_roles_from_firestore_badges(member, firestore_user, roles)

            await add_roles_from_firestore_bundles(member, firestore_user, roles)

        if member.id not in [config.rivers_id]:
            await member.edit(nick=nick)

        # print(nick)
        # print(member)
        # print(member.name)

        # actor_role = next(x for x in roles if x.name == "Actor")

    else:
        print("not MRN")
        nick = await fix_nick(member)

    return member, nick, firestore_user


async def add_og_role_from_firestore_user(member, firestore_user, roles):
    """
    Assign the OG role for rc.com reg date

    """
    print('add_og_role_from_firestore_user')
    if "registeredOn" in firestore_user:

        # A default for firestore user's who are missing registered on for some reason.
        registered_on = datetime.strptime("Sun, 31 Oct 2021 00:00:00 GMT", config.firestore_time_format)

        # replace with the actual if it exists
        if firestore_user["registeredOn"] is not None:
            # Check if registeredOn is already a datetime object (DatetimeWithNanoseconds)
            if hasattr(firestore_user["registeredOn"], 'timestamp'):
                # It's already a datetime object from Firestore, use it directly
                registered_on = firestore_user["registeredOn"]
                # Make sure to convert to naive datetime for comparison with og_cutoff
                if registered_on.tzinfo is not None:
                    registered_on = registered_on.replace(tzinfo=None)
            else:
                # It's a string that needs to be parsed
                registered_on = datetime.strptime(
                    firestore_user["registeredOn"], config.firestore_time_format)
        
        # Sat, 12 Jun 2021 07:00:06 GMT

        if registered_on < config.og_cutoff.replace(tzinfo=None):

            await member.add_roles(next(x for x in roles if x.name == "OG"))


async def add_roles_from_firestore_badges(member, firestore_user, roles):
    """
    Assign any roles they have MRN badges for.
    No way to add Neighbor here unless they have entered the

    """
    print('add_roles_from_firestore_badges')

    member_roles = [x.name for x in member.roles]
    # print(member_roles)

    # # if they don't already have the neighbor role
    # if not member.get(member.roles, name="Neighbor"):

    #     print("miss the neighor role so adding: ", member)

    # # add the Neighbor object to the member
    # await member.add_roles(next(x for x in roles if x.name == "Neighbor"))

    # build a list of strings for each of the roles that the member already has

    # print(member_bundles)
    # member_roles.extend(member_bundles)
    # print(f"roles: {member_roles}")

    # if len(member_roles) > 2:

    # firestore_user = [x for x in firestore_users if x["discordId"] == discord_id]
    # if firestore_user == []:
    #     return
    # print(f"this firestore_user has at least 1 badge: {firestore_user}")

    # The standardize_firestore_user function ensures "badges" exists, so we don't need to check here
    badges = [x for x in firestore_user["badges"] if x != "Visitor"]
    # print(badges)

    for role in badges:
        if role not in member_roles:
            # print(f"Need to add <{role}>")

            try:
                # Create the role object
                role_obj = next(x for x in roles if x.name == role)
                # print("!" + role_obj.name)

                # add the role object to the member
                await member.add_roles(role_obj)
            except Exception as e:
                # print(f'{e}')
                pass
        # else:
        # print(f"Already has <{role}>")


async def add_roles_from_firestore_bundles(member, firestore_user, roles):
    """
    Assign any roles they have Weezify bundles for.
    I can add Neighbor to the discord roles.
    But only if they're connected.
    """
    print('add_roles_from_firestore_bundles')
    # build a list of strings representing the bundle names they own
    member_bundles = [
        config.bundles_map[x] for x in firestore_user["bundleIds"] if x in config.bundles_map
    ]

    # build a list of strings for each of the roles that the member already has
    member_roles = [x.name for x in member.roles]

    # I'm adding the Neighbor role to the member's roles
    # but that doesn't guarantee they will be connected.
    # If not, they will be prompted to connect.
    if member_bundles and "Neighbor" not in member_roles:
        # if they don't already have the neighbor role
        # if not member.get(member.roles, name="Neighbor"):

        # print("miss the neighor role so adding: ", member)

        # db.collection("users").document(firestore_user.id).update(

        # add the Neighbor object to the member
        await member.add_roles(next(x for x in roles if x.name == "Neighbor"))

    for role in member_bundles:
        if role not in member_roles:
            # print(f"Need to add <{role}>")

            try:
                # Create the role object
                role_obj = next(x for x in roles if x.name == role)
                # print(f"!{role_obj.name}")

                # add the role object to the member
                await member.add_roles(role_obj)
            except Exception as e:
                print(e)
        # else:
        #     print(f"Already has <{role}>")


async def delete_bad_roles(member, bad_roles):
    """
    Delete bad roles. A one-time function.
    """

    # member_roles = [x.name for x in member.roles]

    for role in bad_roles:

        # print(member.name, role)
        if role in member.roles:
            print(f"Need to remove <{role}>")

            # add the role object to the member
            await member.remove_roles(role)


async def add_discord_roles_to_firestore_user():
    """
    a one time function to save the accumulated discord service and interest roles to the firestore user records.
    From now on, any additions or removals will be handled by client.on_member_update in bot.py.
    """

    firestore_users = fetch_users()

    discord_roles_to_save_to_firestore = [
        "Srs",
        "Calm",
        "Camp Counselor",
        "Dan",
        "El Scorcho",
        "Artist",
        "Pink Triangle",
        "Writer",
        "Poet",
        "D.J.",
        "Delinquent",
        "gec",
        "Geezer",
        "Musician",
        "Archivist",
        "Tour Guide",
        "Librarian",
        "Curator",
        "Biographical Researcher",
        "Night Watchman",
        "Performer",
        "Parental Advisory",
        "Graphic Design",
        "Data Scientist",
        "Welcome Committee",
        "Creative Director",
    ]
    guild = client.get_guild(config.GUILD_ID)

    members = guild.members
    # print(len(members))

    for member in members:

        # If they don't have more than 5 roles, skip them.
        if len(member.roles) < 5:
            continue

        roles = [
            x.name for x in member.roles if x.name in discord_roles_to_save_to_firestore
        ]

        if not roles:
            continue

        # Get the firestore user dictionary that corresponds to this discord user.
        discord_id = str(member)

        if firestore_user := get_firestore_user(discord_id, firestore_users):
            # print(firestore_user)
            id = firestore_user["id"]

            db = get_firestore_db()

            if ref := db.collection("users").document(id).get():
                ref.reference.update({"badges": firestore.ArrayUnion(roles)})
            else:
                print(f"No firestore user record with firestore id {id}")
