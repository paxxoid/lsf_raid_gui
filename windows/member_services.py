import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFile, Qt, QDate
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QLineEdit,
    QTextEdit,
    QLabel,
    QComboBox,
    QPushButton,
    QTableWidget, 
    QCompleter,
    QTableWidgetItem,
    QDateEdit,
    QCheckBox,
    QSpinBox, QMessageBox
)

from helpers.app_state import AppState


class MemberServices:
    def __init__(self,  yaml_data, logger, app_state, api_client, parent=None,):
        self.window = self._load_window(parent)
        self.yaml_data = yaml_data
        self.logger = logger
        self.app_state = app_state
        self.api_client = api_client

        self._setup_widget_references()
        self._connect_signals()
        self._load_player_combo()
        self._load_static_combos()
        #self._setup_player_search()


    def _setup_widget_references(self):    
        self.combo_select_current_users = self.window.findChild(QComboBox, "combo_select_current_users")
        self.text_character_name = self.window.findChild(QLineEdit, "text_character_name")
        self.combo_character_type = self.window.findChild(QComboBox, "combo_character_type")
        self.combo_main_character = self.window.findChild(QComboBox, "combo_main_character")
        self.combo_class = self.window.findChild(QComboBox, "combo_class")
        self.combo_race = self.window.findChild(QComboBox, "combo_race")
        self.combo_guild_rank = self.window.findChild(QComboBox, "combo_guild_rank")
        self.date_joined = self.window.findChild(QDateEdit, "date_joined")
        self.checkBox_raider = self.window.findChild(QCheckBox, "checkBox_raider")
        self.text_bio = self.window.findChild(QTextEdit, "text_bio")
        self.check_active = self.window.findChild(QCheckBox, "check_active")
        self.member_level = self.window.findChild(QSpinBox, "member_level")

        self.button_save_data = self.window.findChild(QPushButton, "button_save_data")

    def _connect_signals(self):

        self.date_joined.setDate(
            QDate.currentDate()
        )
        self.button_save_data.clicked.connect(
            self._button_save_data
        )

        self.combo_select_current_users.currentIndexChanged.connect(
            self._load_existing_player_data
        )

        self.text_character_name.textEdited.connect(
            self._player_search_text_changed
        )        


    def _player_search_text_changed(self):
        if self.combo_select_current_users.currentIndex() > 0:
            self.combo_guild_rank.setCurrentIndex(0)
            self.combo_character_type.setCurrentIndex(0)
            self.combo_race.setCurrentIndex(0)
            self.combo_class.setCurrentIndex(0)
            self.combo_select_current_users.setCurrentIndex(0)
            self.date_joined.clear()
            self.text_bio.clear()


    
    def _load_existing_player_data(self, index):
        selected_text = self.combo_select_current_users.itemText(index)
        selected_data = self.combo_select_current_users.itemData(index)
        print(selected_data)
        if selected_data:
            self.text_character_name.setText(str(selected_data['character_name']))

            character_type = selected_data["character_type"]
            character_class = selected_data["class_name"]
            character_race = selected_data["race"]
            guild_rank = selected_data["rank"]
            ckbox_raider = selected_data["raider"]
            ckbox_active = selected_data["active"]            
            character_main = selected_data['main_character']
            joined = selected_data['joined_at']
            

            index = self.combo_character_type.findData(character_type)
            if index >= 0:
                self.combo_character_type.setCurrentIndex(index)

            index = self.combo_class.findData(character_class)
            if index >= 0:
                self.combo_class.setCurrentIndex(index)   

            index = self.combo_race.findData(character_race)
            if index >= 0:
                self.combo_race.setCurrentIndex(index)                                  

            index = self.combo_guild_rank.findData(guild_rank)
            if index >= 0:
                self.combo_guild_rank.setCurrentIndex(index)      

            index = self.combo_guild_rank.findData(guild_rank)
            if index >= 0:
                self.combo_guild_rank.setCurrentIndex(index)  

            # index = self.combo_main_character.findData(character_main)

            # print(f"index {index} - {character_main}")
            # if index >= 0:
            #     self.combo_main_character.setCurrentIndex(index)          

            # character_main = selected_data.get("main_character")

            if character_main:
                index = self.find_player_index(
                    self.combo_main_character,
                    character_main,
                )

                if index >= 0:
                    self.combo_main_character.setCurrentIndex(index)
            else:
                self.combo_main_character.setCurrentIndex(0)                        

            if ckbox_raider:
                self.checkBox_raider.setChecked(True)
            else:
                self.checkBox_raider.setChecked(False)

            if ckbox_active:
                self.check_active.setChecked(True)
            else:
                self.check_active.setChecked(False)                

            self.member_level.setValue(selected_data['level'])

            date_value = QDate.fromString(
                str(joined),
                "yyyy-MM-dd",
            )

            if date_value.isValid():
                self.date_joined.setDate(date_value)

            print(f"joined: {joined} - date_value {date_value} - date_value.isValid() {date_value.isValid()} ")
            
        

    def _button_save_data(self):
        character_name = self.text_character_name.text().strip()
        selected_data = self.combo_select_current_users.currentData()
        main_character = self.combo_main_character.currentText()
        selected_class = self.combo_class.currentText().lower()
        selected_type = self.combo_character_type.currentText().lower()
        select_rank = self.combo_guild_rank.currentText().lower()
        active = self.check_active.isChecked()
        raider = self.checkBox_raider.isChecked()
        level = self.member_level.value()
        bio = self.text_bio.toPlainText().strip()
        race = self.combo_race.currentText().lower()
        selected_date = self.date_joined.date().toString("yyyy-MM-dd")
        current_date = datetime.now().strftime("%Y-%m-%d")

        #main_character_id =  list(filter(lambda record: record.get("main_character_id") == main_character, self.app_state.PLAYER_RECORDS))

        main_character_record = next(
            (
                record
                for record in self.app_state.PLAYER_RECORDS
                if record.get("character_name", "").casefold()
                 == main_character.casefold()
            ),
             None,
        )

        main_character_id = (
            main_character_record["id"]
            if main_character_record
            else None
        )     

        if self.combo_select_current_users.currentIndex() > 0:  #update existing user
   
            # print("----- Member Form Debug -----")
            # print(f"member_id: {selected_data['id']}")
            # print(f"main_character_id {main_character_id}")
            # print(f"main_character: {main_character!r} | type: {type(main_character).__name__}")
            # print(f"selected_class: {selected_class!r} | type: {type(selected_class).__name__}")
            # print(f"selected_type: {selected_type!r} | type: {type(selected_type).__name__}")
            # print(f"select_rank: {select_rank!r} | type: {type(select_rank).__name__}")
            # print(f"active: {active!r} | type: {type(active).__name__}")
            # print(f"raider: {raider!r} | type: {type(raider).__name__}")
            # print(f"level: {level!r} | type: {type(level).__name__}")
            # print(f"bio: {bio!r} | type: {type(bio).__name__}")
            # print(f"race: {race!r} | type: {type(race).__name__}")
            # print("-----------------------------")

            try:

                results = self.api_client.patch (
                            f"/api/v1/members/{selected_data['id']}",
                            json_data={
                                "character_type": selected_type,
                                "main_character_id": main_character_id,
                                "class_name": selected_class,
                                "race": race,
                                "level": level,
                                "rank": select_rank,
                                "active": active,
                                "raider": raider,
                                "bio": bio,
                                "joined_at": selected_date
                            }
                )
            
                
                if "id" in results:
                    self.logger.log_to_file(
                                "INFO", 
                                    [
                                        f"Member Updated!",
                                        f"Update Info: {json.dumps(results, indent=2)}"
                                    ]
                                )
                    QMessageBox.information(
                        self.window,
                        "Player Updated!",
                        f"ID {results['id']} {results['character_name']} successfully updated! \n\n Review log tab for more details.",
                    )                         
                    self.app_state.load_app_state()
            except Exception as e:
                self.logger.log_to_file(
                    "WARNING", 
                        [
                            f"API Error updating existing member!",
                            f"The error: {str(e)}"
                        ]
                    )
                QMessageBox.warning(
                    self.window,
                    "New player was NOT updated!",
                    f"Review log tab for more details.",
                    )                    
        else:
            try:
                results = self.api_client.post (
                            f"/api/v1/members/create",
                            json_data={
                                "character_name": character_name,
                                "character_type": selected_type,
                                "main_character_id": main_character_id,
                                "class_name": selected_class,
                                "race": race,
                                "level": level,
                                "rank": select_rank,
                                "active": active,
                                "raider": raider,
                                "bio": bio,
                                "joined_at": current_date
                            }
                )
                
                if "id" in results:
                    self.logger.log_to_file(
                                "INFO", 
                                    [
                                        f"Member Added!",
                                        f"Update Info: {json.dumps(results, indent=2)}"
                                    ]
                                )  
                    QMessageBox.information(
                        self.window,
                        "New player added!",
                        f"ID {results['id']} - {results['character_name']} successfully Added! \n\n Review log tab for more details.",
                    )                              
                                
                    self.app_state.load_app_state()

            except Exception as e:
                self.logger.log_to_file(
                    "WARNING", 
                        [
                            f"API Error adding a new member!",
                            f"The error: {str(e)}"
                        ]
                    )     
                QMessageBox.warning(
                    self.window,
                    "New player was NOT added!",
                    f"Review log tab for more details.",
                )    
                    



    def find_player_index(self,combo_box, character_name):
        for index in range(combo_box.count()):
            player_data = combo_box.itemData(index)

            if not isinstance(player_data, dict):
                continue

            if (
                player_data.get("character_name", "").casefold()
                == character_name.casefold()
            ):
                return index

        return -1

    def _load_static_combos(self):

        #class combo
        self.combo_class.clear()
        self.combo_class.addItem("Select Class", None)
        self.combo_class.addItem("Bard", "bard")
        self.combo_class.addItem("Beastlord", "beastlord")
        self.combo_class.addItem("Cleric", "cleric")
        self.combo_class.addItem("Druid", "druid")
        self.combo_class.addItem("Enchanter", "enchanter")
        self.combo_class.addItem("Magician", "magician")
        self.combo_class.addItem("Monk", "monk")
        self.combo_class.addItem("Necromancer", "necromancer")
        self.combo_class.addItem("Paladin", "paladin")
        self.combo_class.addItem("Ranger", "ranger")
        self.combo_class.addItem("Rogue", "rogue")
        self.combo_class.addItem("Shadow Knight", "shadowknight")
        self.combo_class.addItem("Shaman", "shaman")
        self.combo_class.addItem("Warrior", "warrior")
        self.combo_class.addItem("Wizard", "wizard")
        self.combo_class.setCurrentIndex(0)

        #race combo
        self.combo_race.clear()
        self.combo_race.addItem("Select Race", None)
        self.combo_race.addItem("Barbarian", "barbarian")
        self.combo_race.addItem("Dark Elf", "dark_elf")
        self.combo_race.addItem("Dwarf", "dwarf")
        self.combo_race.addItem("Erudite", "erudite")
        self.combo_race.addItem("Gnome", "gnome")
        self.combo_race.addItem("Half Elf", "half_elf")
        self.combo_race.addItem("Halfling", "halfling")
        self.combo_race.addItem("High Elf", "high_elf")
        self.combo_race.addItem("Human", "human")
        self.combo_race.addItem("Ogre", "ogre")
        self.combo_race.addItem("Troll", "troll")
        self.combo_race.addItem("Wood Elf", "wood_elf")
        self.combo_race.setCurrentIndex(0)

        #maintype
        self.combo_character_type.clear()
        self.combo_character_type.addItem("Main", "main")
        self.combo_character_type.addItem("Alt", "alt")
        self.combo_character_type.setCurrentIndex(0)

        #guild ranks
        self.combo_guild_rank.clear()
        self.combo_guild_rank.addItem("Recruit", "recruit")
        self.combo_guild_rank.addItem("Member", "member")
        self.combo_guild_rank.addItem("Raider", "raider")
        self.combo_guild_rank.addItem("Officer", "officer")
        self.combo_guild_rank.addItem("Guild Leader", "guild leader")
        self.combo_guild_rank.setCurrentIndex(0)






    def _load_player_combo(self):
        self.combo_select_current_users.insertItem(0, "Select Member", None)
        self.combo_main_character.insertItem(0, "Select Member", None)
        for  player in self.app_state.PLAYER_RECORDS:
           # print(player)
            player_data = {
                "id": player["id"],
                "character_name": player["character_name"],
                "character_type": player["character_type"],
                "character_type_display": player["character_type_display"],
                "main_character_id": player["main_character_id"],
                "main_character": player["main_character"],
                "class_name": player["class_name"],
                "class_name_display": player["class_name_display"],
                "race": player["race"],
                "level": player["level"],
                "rank": player["rank"],
                "rank_display": player["rank_display"],
                "active": player["active"],
                "raider": player["raider"],
                "featured": player["featured"],
                "joined_at": player["joined_at"],
                "bio": player["bio"],
                "last_raid_attended": player["last_raid_attended"],
            }            
            self.combo_select_current_users.addItem(player['character_name'], 
                                            player_data
                                       )      
            self.combo_main_character.addItem(f"{player['character_name']}", 
                                            player_data
                            )     


    def _load_window(self, parent=None):
        ui_path = Path(__file__).with_name(
            "member_services.ui"
        )

        loader = QUiLoader()
        ui_file = QFile(str(ui_path))

        if not ui_file.open(QFile.OpenModeFlag.ReadOnly):
            raise RuntimeError(
                f"Could not open UI file: {ui_path}"
            )

        window = loader.load(ui_file, parent)
        ui_file.close()

        if window is None:
            raise RuntimeError(
                "Failed to load player search UI"
            )

        # Completely destroy the window when closed.
        window.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            True,
        )

        return window

    def show(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()    



