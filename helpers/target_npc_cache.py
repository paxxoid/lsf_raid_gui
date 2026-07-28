class TargetNpcCache:
    def __init__(self, api_client, logger):
        self.api_client = api_client
        self.logger = logger

        self.current_zone = None
        self.npc_names = set()

    @staticmethod
    def normalize_name(name):
        return " ".join(name.strip().split()).casefold()

    def load_zone(self, zone_name):
        normalized_zone = self.normalize_name(zone_name)

        if normalized_zone == self.current_zone:
            return

        self.current_zone = normalized_zone
        self.npc_names.clear()

        try:
            results = self.api_client.get(
                "/api/v1/quarm/npcs-simple",
                params={
                    "zone": zone_name,
                },
            )
            names = results.get("names", [])
            self.npc_names = {
                self.normalize_name(name)
                for name in names
                if isinstance(name, str) and name.strip()
            }            

            self.logger.log_to_file(
                "info",
                f"Loaded {len(self.npc_names)} NPC names "
                f"for {zone_name}"
            )

        except Exception as error:

            self.logger.log_to_file(
                "warning",
                    [
                        f"Could not load NPC names for {zone_name}: "
                        f"Error:  {error}"
                   ]
                )                     
    def is_known_npc(self, target_name):
        return self.normalize_name(target_name) in self.npc_names