import csv
import re
from django.core.management.base import BaseCommand


raw_data = """
Alibori Department

Banikoara
Banikoara, Founougo, Gomparou, Goumori, Kokey, Kokiborou, Ounet, Sompérékou, Soroko, Toura

Gogounou
Bagou, Gogounou, Gounarou, Ouara, Sori, Zoungou-Pantrossi

Kandi
Angaradébou, Bensékou, Donwari, Kandi I, Kandi II, Kandi III, Kassakou, Saah, Sam, Sonsoro

Karimama
Birni-Lafia, Bogo-Bogo, Karimama, Kompa, Monsey

Malanville
Garou, Guénè, Malanville, Mandécali, Tomboutou

Ségbana
Libantè, Liboussou, Lougou, Ségbana, Sokotindji


Atakora Department

Boukoumbé
Boukoumbé, Dipoli, Korontière, Kossoucoingou, Manta, Natta, Tabota

Cobly
Cobly, Datori, Kountori, Tapoga

Kérou
Brignamaro, Firou, Kérou, Koabagou

Kouandé
Birni, Chabi-Couma, Fô-Tancé, Guilmaro, Kouandé, Oroukayo

Matéri
Dassari, Gouandé, Matéri, Nodi, Tantéga, Tchianhoun-Cossi

Natitingou
Kotapounga, Kouaba, Koundata, Natitingou I, Natitingou II, Natitingou III, Natitingou IV, Perma, Tchoumi-Tchoumi

Péhunco
Gnémasson, Péhunco, Tobré

Tanguiéta
Cotiakou, N'Dahonta, Taiakou, Tanguiéta, Tanongou

Toucountouna
Kouarfa, Tampégré, Toucountouna


Atlantique Department

Abomey-Calavi
Abomey-Calavi, Akassato, Godomey, Glo-Djigbé, Hévié, Kpanroun, Ouédo, Togba, Zinvié

Allada
Agbanou, Ahouannonzoun, Allada, Attogon, Avakpa, Ayou, Hinvi, Lissègazoun, Lon-Agonmey, Sékou, Togoudo, Tokpa-Avagoudo

Kpomassè
Aganmalomè, Agbanto, Agonkanmè, Dedomè, Dekanmè, Kpomassè, Ségbeya, Ségbohoué, Tokpa-Domè

Ouidah
Avlékété, Djégbadji, Gakpè, Ouakpé-Daho, Ouidah I, Ouidah II, Ouidah III, Ouidah IV, Pahou, Savi

Sô-Ava
Ahomey-Lokpo, Dékanmey, Ganvié I, Ganvié II, Houédo-Aguékon, Sô-Ava, Vekky

Toffo
Agué, Colli-Agbamè, Coussi, Damè, Djanglanmè, Houégbo, Kpomé, Sè, Séhouè, Toffo-Agué

Tori-Bossito
Avamè, Azohouè-Aliho, Azohouè-Cada, Tori-Bossito, Tori-Cada, Tori-Gare
Zè

Adjan, Dawé, Djigbé, Dodji-Bata, Hékanmè, Koundokpoè, Sèdjè-Dénou, Sèdjè-Houégoudo, Tangbo-Djevié, Yokpo, Zè


Borgou Department

Bembèrèkè
Bembèrèkè, Béroubouay, Bouanri, Gomia, Ina

Kalalè
Basso, Bouka, Dèrassi, Dunkassa, Kalalè, Péonga

N'Dali
Bori, Gbégourou, N'Dali, Ouénou, Sirarou

Nikki
Biro, Gnonkourakali, Nikki, Ouénou, Sérékalé, Suya, Tasso

Parakou
1st arrondissement, 2nd arrondissement, 3rd arrondissement

Pèrèrè
Gninsy, Guinagourou, Kpané, Pébié, Pèrèrè, Sontou

Sinendé
Fô-Bourè, Sèkèrè, Sikki, Sinendé

Tchaourou
Alafiarou, Bétérou, Goro, Kika, Sanson, Tchaourou, Tchatchou


Collines Department

Bantè
Agoua, Akpassi, Atokoligbé, Bantè, Bobè, Gouka, Koko, Lougba, Pira

Dassa-Zoumè
Akofodjoulè, Dassa I, Dassa II, Gbaffo, Kèrè, Kpingni, Lèma, Paouingnan, Soclogbo, Tré

Glazoué
Aklankpa, Assanté, Glazoué, Gomè, Kpakpaza, Magoumi, Ouèdèmè, Sokponta, Thio, Zaffé

Ouèssè
Challa-Ogoi, Djègbè, Gbanlin, Kèmon, Kilibo, Laminou, Odougba, Ouèssè, Toui

Savalou
Djaloukou, Doumè, Gobada, Kpataba, Lahotan, Lèma, Logozohoué, Monkpa, Ottola, Ouèssè, Savalou-Aga, Savalou-Agbado, Savalou-Attakè, Tchetti

Savé
Adido, Bèssè, Boni, Kaboua, Ofè, Okpara, Plateau, Sakin


Donga Department

Bassila
Alédjo, Bassila, Manigri, Pénéssoulou

Copargo
Anandana, Copargo, Pabégou, Singré

Djougou
Barei, Bariénou, Bélléfoungou, Bougou, Djougou I, Djougou II, Djougou III, Kolokondé, Onklou, Patargo, Pélébina, Sérou

Ouaké
Badjoudè, Kondé, Ouaké, Sèmèrè I, Sèmèrè II, Tchalinga


Kouffo Department

Aplahoué
Aplahoué, Atomè, Azovè, Dekpo, Godohou, Kissamey, Lonkly

Djakotomey
Adjintimey, Bètoumey, Djakotomey I, Djakotomey II, Gohomey, Houègamey, Kinkinhoué, Kokohoué, Kpoba, Sokouhoué

Dogbo
Ayomi, Dèvè, Honton, Lokogohoué, Madjrè, Tota, Totchagni

Klouékanmè
Adjanhonmè, Ahogbèya, Aya-Hohoué, Djotto, Hondji, Klouékanmè, Lanta, Tchikpé

Lalo
Adoukandji, Ahondjinnako, Ahomadégbé, Banigbé, Gnizounmè, Hlassamè, Lalo, Lokogba, Tchito, Tohou, Zalli

Toviklin
Adjido, Avédjin, Doko, Houédogli, Missinko, Tannou-Gola, Toviklin


Littoral Department

Cotonou
1st arrondissement, 2nd arrondissement, 3rd arrondissement, 4th arrondissement, 5th arrondissement, 6th arrondissement, 7th arrondissement, 8th arrondissement, 9th arrondissement, 10th arrondissement, 11th arrondissement, 12th arrondissement, 13th arrondissement


Mono Department

Athiémè
Adohoun, Atchannou, Athiémè, Dédékpoé, Kpinnou

Bopa
Agbodji, Badazoui, Bopa, Gbakpodji, Lobogo, Possotomè, Yégodoé

Comè
Agatogbo, Akodéha, Comè, Ouèdèmè-Pédah, Oumako

Grand-Popo
Adjaha, Agoué, Avloh, Djanglanmey, Gbéhoué, Grand-Popo, Sazoué

Houéyogbé
Dahé, Doutou, Honhoué, Houéyogbé, Sè, Zoungbonou

Lokossa
Agamé, Houin, Houèdèmè-Adja, Koudo, Lokossa


Ouémé Department

Adjarra
Adjarra I, Adjarra II, Aglogbé, Honvié, Malanhoui, Médédjonou

Adjohoun
Adjohoun, Akpadanou, Awonou, Azowlissè, Dèmè, Gangban, Kodè, Togbota

Aguegues
Avagbodji, Houédomè, Zoungamè

Akpro-Missérété
Akpro-Missérété, Gomè-Sota, Katagon, Vakon, Zoungbomè

Avrankou
Atchoukpa, Avrankou, Djomon, Gbozounmè, Kouty, Ouanho, Sado

Bonou
Affamè, Atchonsa, Bonou, Damè-Wogon, Houinviguè

Dangbo
Dangbo, Dékin, Gbéko, Houédomey, Hozin, Késsounou, Zounguè

Porto-Novo
1st arrondissement, 2nd arrondissement, 3rd arrondissement, 4th arrondissement, 5th arrondissement

Sèmè-Kpodji
Agblangandan, Aholouyèmè, Djrègbè, Ekpè, Sèmè-Kpodji, Tohouè


Plateau Department

Adja-Ouèrè
Adja-Ouèrè, Ikpinlè, Kpoulou, Massè, Oko-Akarè, Totonnoukon

Ifangni
Banigbé, Daagbé, Ifangni, Ko-Koumolou, Lagbé, Tchaada

Kétou
Adakplamé, Idigny, Kpankou, Kétou, Odometa, Okpometa

Pobè
Ahoyéyé, Igana, Issaba, Pobè, Towé

Sakété
Aguidi, Ita-Djèbou, Sakété I, Sakété II, Takon, Yoko


Zou Department

Abomey
Agbokpa, Dètohou, Djègbè, Hounli, Sèhoun, Vidolè, Zounzounmè

Agbangnizoun
Adahondjigon, Adingningon, Agbangnizoun, Kinta, Kpota, Lissazounmè, Sahé, Siwé, Tanvé, Zoungoudo

Bohicon
Agongointo, Avogbana, Bohicon I, Bohicon II, Gnidjazoun, Lissèzoun, Ouassaho, Passagon, Saclo, Sodohomè

Covè
Adogbé, Gounli, Houéko, Houen-Hounso, Lainta-Cogbè, Naogon, Soli, Zogba

Djidja
Agondji, Agouna, Dan, Djidja, Dohouimè, Gobè, Monsourou, Mougnon, Oungbègamè, Outo, Setto, Zoukou

Ouinhi
Dasso, Ouinhi, Sagon, Tohoué

Za-Kpota
Allahé, Assalin, Houngomey, Kpakpamè, Kpozoun, Za-Kpota, Za-Tanta, Zèko

Zagnanado
Agonli-Houégbo, Banamè, Don-Tan, Dovi, Kpédékpo, Zagnanado

Zogbodomey
Akiza, Avlamè, Cana I, Cana II, Domè, Koussoukpa, Kpokissa, Massi, Tanwé-Hessou, Zogbodomey, Zoukou
"""


class Command(BaseCommand):
    rows = []
    current_department = ""
    current_commune = ""

    def handle(self, *args, **kwargs):
        lines = raw_data.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Detect department
            if "Department" in line:
                self.current_department = line.replace(" Department", "").strip()
            # Detect commune
            elif re.match(r'^[A-Z]', line) and ',' not in line:
                self.current_commune = line.strip()
            # Detect arrondissement list
            else:
                arrondissements = [a.strip() for a in line.split(',')]
                for arrondissement in arrondissements:
                    self.rows.append([self.current_department, self.current_commune, arrondissement])

        # Save to CSV
        with open("administrativelevels/management/benin_admin_divisions.csv",
                  mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Department", "Commune", "Arrondissement"])
            writer.writerows(self.rows)
