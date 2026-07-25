from helpers.api_factory import APIClient, APIClientError

class AppState:
    def __init__(self, logger):
        # Application-wide variables
        self.current_character = None
        self.current_raid_id = None
        self.api_key = "lasf_LGLjVSi6LbgbDOs4MbtFY8QS7YKCwrRFY6kjooPW_Z0"
        self.raid_members = []
        self.zeal_filters = []
        self.is_connected = False
        self.PLAYER_RECORDS = []
        self.raid_attendance = []
        self.loot_records = []
        self.rais_scheduled = []

        self.logger = logger

        self.load_app_state()

    def load_app_state(self):
        """Load the application state from a file or database."""
        # For now, we will just return a new instance of AppState.
        # In a real application, you would load the state from a file or database.
    
        client = APIClient(
                base_url="https://lootandsomefun.com",
                api_key= self.api_key,
            )
        try:
                self.PLAYER_RECORDS = client.get(
                    "/api/v1/members",
                    params={
                        "limit": 100,
                        "offset": 0,
                    },
                )

                self.raid_attendance = client.get(
                    "/api/v1/attendance",
                    params={
                        "limit": 100,
                        "offset": 0,
                    },
                )

                self.loot_records = client.get(
                    "/api/v1/loot",
                    params={
                        "limit": 100,
                        "offset": 0,
                    },
                )

                self.raid_scheduled = client.get(
                    "/api/v1/raids",
                    params={
                        "limit": 500,
                        "offset": 0,
                    },
                )                

        except APIClientError as exc:
                print(exc)

        
        finally:
            client.close()                    

        print(f"Loaded {len(self.PLAYER_RECORDS)} player records from the API.")
        print(f"First player record: {self.PLAYER_RECORDS[0] if self.PLAYER_RECORDS else 'No records found.'}")

        print(f"Loaded {len(self.raid_attendance)} raid attendance records from the API.")
        print(f"First raid attendance record: {self.raid_attendance[0] if self.raid_attendance else 'No records found.'}")
        print(f"Loaded {len(self.loot_records)} loot records from the API.")
        print(f"First loot record: {self.loot_records[0] if self.loot_records else 'No records found.'}")

