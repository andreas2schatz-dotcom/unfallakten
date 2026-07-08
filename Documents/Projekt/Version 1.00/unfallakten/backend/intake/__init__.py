"""
Intake-Pipeline (Pipeline-Refactoring v7, Stufe 1).

Dieses Paket buendelt die neue Intake-Schicht:
  * ``archiv``          Original-Archiv + Normalisierung auf Arbeitskopie (S1.2)
  * ``adapter_imap``    IMAP-Adapter: Body + Anhaenge -> intake_dokumente/zustellungen (S1.3)
  * ``adapter_upload``  Upload-Adapter: Datei -> intake_dokumente/zustellungen (S1.3)
  * ``adapter_eakte``   E-Akte-Adapter: raEloakte-PDF -> intake_dokumente/zustellungen (S1.3)
  * (Folgeschritte)     Absender-Registry, Klassen-Registry, Queue, Pipeline ...
"""
