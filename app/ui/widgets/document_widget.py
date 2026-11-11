        self.data = data
        self.year = data["year"]
        self.month = data["month"]
        self.group = data["group"]
        self.doc_type = data["doc_type"]
        self.manual_mode = data["manual_mode"]
        self.last_day = calendar.monthrange(self.year, self.month)[1]

        inst_num = data.get("instance_number", 0)
        suffix = f" ({inst_num})" if inst_num > 0 else ""

        if self.doc_type == "schedule":
            title = (f"График группы по охранному обеспечению "
                     f"на {MONTHS_RU[self.month - 1]} {self.year} г.{suffix}")
            self.summary_keys = ["Факт. работы", "Отпуск", "Всего",
                                 "Норма", "Ознакомлен"]
        elif self.group == "security":
            title = (f"Табель группы по охранному обеспечению "
                     f"на {MONTHS_RU[self.month - 1]} {self.year} г.{suffix}")
            self.summary_keys = [
                "Факт. работы", "Медицинский осмотр", "Болезнь", "Справка",
                "Отпуск", "Прогул", "Отпуск без сохранения з/п",
                "Всего", "Норма", "Переработка", "Работа в ночь",
                "Работа в праздничные дни"]
        else:
            title = (f"Табель транспортной группы "
                     f"на {MONTHS_RU[self.month - 1]} {self.year} г.{suffix}")
            self.summary_keys = [
                "Факт. работы, дни", "Командировка, дни",
                "Разъездной характер работы", "Расчет по среднему",
                "Медицинский осмотр", "Болезнь", "Отпуск",
                "Отпуск без сохранения з/п", "Прогул",
                "Факт. время, часов", "Норма, часов"]
