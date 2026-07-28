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
                "/api/v1/quarm/npcs",
                params={
                    "zone": zone_name,
                    "limit": 5000,
                },
            )

            self.npc_names = {
                self.normalize_name(npc["name"])
                for npc in results
                if npc.get("name")
            }

            self.logger.debug(
                f"Loaded {len(self.npc_names)} NPC names "
                f"for {zone_name}"
            )

        except Exception as error:
            self.logger.warning(
                f"Could not load NPC names for {zone_name}: {error}"
            )

    def is_known_npc(self, target_name):
        return self.normalize_name(target_name) in self.npc_names