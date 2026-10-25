# Use Case CoppeliaSim dan Roadmap Fitur MCP

## Ringkasan

CoppeliaSim digunakan untuk membangun, mengendalikan, dan menguji sistem robot dalam simulasi. Manual resminya menyebut otomasi pabrik, prototyping dan verifikasi, pengembangan algoritma, pemantauan jarak jauh, kontrol hardware, pendidikan robotika, dan presentasi produk sebagai aplikasi. Ini daftar aplikasi yang didukung, bukan peringkat pemakaian. Sumber yang diperiksa tidak menyediakan statistik tentang use case yang paling populer.

Contoh nyata yang tersedia dalam dokumentasi dan scene resmi mencakup pick-and-place, perencanaan jalur, simulasi sensor, ROS 2, dan kontrol robot melalui aplikasi eksternal.

## Penggunaan yang didukung sumber resmi

| Area penggunaan | Contoh workflow | Sumber |
|---|---|---|
| Otomasi industri | Simulasikan lini otomasi, robot, conveyor, dan tugas pick-and-place sebelum commissioning fisik. | [Virtual commissioning](https://coppeliarobotics.com/virtual-commissioning-of-custom-automation-lines), [scene resmi](https://github.com/CoppeliaRobotics/scenes) |
| Prototyping dan verifikasi | Ubah model mekatronika, uji konfigurasi, dan evaluasi perilaku sebelum membuat prototipe fisik. | [Fast prototyping](https://coppeliarobotics.com/fast-prototyping-of-mechatronics-systems) |
| Kinematika dan motion planning | Gunakan IK untuk mencari konfigurasi robot dan OMPL untuk menghitung jalur dengan batas collision. | [Fitur utama](https://manual.coppeliarobotics.com/en/coppeliaSimFeatures.htm), [motion planning](https://manual.coppeliarobotics.com/en/pathAndMotionPlanningModules.htm) |
| Persepsi dan sensor | Uji proximity sensor, kamera, image processing, depth, serta point-cloud workflow. | [Vision sensor](https://manual.coppeliarobotics.com/en/visionSensors.htm), [scene resmi](https://github.com/CoppeliaRobotics/scenes) |
| Kontrol eksternal | Hubungkan controller Python atau ROS 2 ke robot simulasi melalui remote API, topic, service, atau action. | [External controller](https://manual.coppeliarobotics.com/en/externalControllerTutorial.htm), [ROS 2](https://manual.coppeliarobotics.com/en/ros2Interface.htm) |
| Pendidikan dan riset | Pelajari robotika dan uji algoritma melalui tutorial serta scene simulasi yang dapat dikendalikan dengan script. | [Tutorial resmi](https://manual.coppeliarobotics.com/en/tutorials.htm), [riset CoppeliaSim](https://coppeliarobotics.com/research) |
| Digital twin dan monitoring | Hubungkan representasi simulasi dengan alur validasi atau pemantauan sistem otomatisasi. | [Aplikasi pada manual](https://manual.coppeliarobotics.com/en/welcome.htm), [virtual commissioning](https://coppeliarobotics.com/virtual-commissioning-of-custom-automation-lines) |

Manual juga menjelaskan lima engine fisika dan fitur collision, minimum distance, sensor, data recording, serta impor/ekspor model. [Fitur utama](https://manual.coppeliarobotics.com/en/coppeliaSimFeatures.htm) · [Dynamics](https://manual.coppeliarobotics.com/en/dynamicsModule.htm) · [Import/export](https://manual.coppeliarobotics.com/en/importExport.htm)

**Batas kesimpulan:** sumber resmi dan contoh scene menunjukkan kemampuan serta workflow yang didukung. Sumber tersebut tidak membuktikan frekuensi penggunaannya di komunitas atau menentukan sektor yang paling banyak memakai CoppeliaSim.

## Kondisi MCP saat ini

Audit implementasi dan dokumentasi proyek menunjukkan fitur berikut sudah tersedia:

- `coppelia_step`: eksekusi Python, snapshot gambar MCP, diagnostics collision/distance/floor, timeout, dan cancellation.
- `coppelia_simulate`: simulasi bertahap, pengambilan posisi dan proximity sensor, serta penghentian berdasarkan kondisi.
- `coppelia_catalog` dan `coppelia_scene`: pencarian model/scene serta save/load scene.
- `coppelia_health`: pemeriksaan koneksi ZeroMQ, versi runtime, dan ketersediaan `simIK`/`simOMPL`.
- `coppelia_motion`: IK dan perencanaan path joint melalui OMPL.
- `coppelia_trajectory`: trajectory berbatas joint, velocity, serta opsional acceleration/jerk; collision, grasp kontak-dinamis, lift/hold, wrench sweep, dan place.
- `coppelia_record_dataset`: rekaman state serta sensor bertipe yang tersinkron per langkah simulasi, dengan timestamp, metadata, batas sampel, dan ekspor JSON.
- `coppelia_ros2`: operasi satu-shot dan alur capture/publish sequence/closed-loop feedback dengan batas jumlah serta durasi.
- `coppelia_sensors`: pembacaan proximity, RGB, depth metrik, gaya/torsi, dan point cloud kamera bertipe.
- `coppelia_mechanism`: ringkasan joint, batas, posisi/target, sensor, serta kandidat base dan end-effector pada subtree robot.
- `coppelia_experiments`: batch hingga 20 episode dan 10.000 langkah gabungan, baseline scene eksplisit, reset scene per episode, serta assertions tugas pada objek atau proximity sensor.

Pemeriksaan proximity tidak membuktikan objek terpasang pada gripper atau menjamin keselamatan hardware.

## Fitur MCP dan kondisi dukungan

| Prioritas | Fitur | Kebutuhan pengguna | Kondisi MCP |
|---|---|---|---|
| **P0** | Eksekusi trajectory dan tugas manipulasi | Jalankan path robot dengan batas gerak, pantau collision, kendalikan gripper, dan periksa hasil grasp/place. | `coppelia_trajectory` memeriksa kontak dinamis dan retensi setelah lift; place masih berbasis jarak. |
| **P1** | Pembacaan sensor bertipe | Ambil data vision RGB/depth, force/torque, dan point cloud tanpa menulis script khusus setiap kali. | Tersedia melalui `coppelia_sensors`; payload point cloud dibatasi dan memakai sampling piksel. |
| **P1** | Inspeksi mekanisme robot | Temukan joint, jenis dan batasnya, posisi/target, sensor, base, dan end-effector sebelum mengendalikan model. | Tersedia melalui `coppelia_mechanism`; end-effector dilaporkan sebagai kandidat leaf, bukan identifikasi semantik otomatis. |
| **P1** | Batch eksperimen dan evaluasi skenario | Ulangi simulasi dengan kondisi berbeda, ukur keberhasilan/waktu, lalu bandingkan diagnostic stop. | `coppelia_experiments` memuat ulang baseline scene per episode dan memeriksa assertions tugas. |
| **P2** | Impor model robot terstruktur | Muat URDF/SDF atau aset mesh, lalu laporkan model dan joint yang berhasil diimpor. | `coppelia_import_model` mendukung URDF, SDF, STL, OBJ, dan DAE; melaporkan root baru serta hitungan joint. |
| **P2** | Integrasi ROS 2 opsional | Hubungkan topic, service, atau action untuk menguji controller ROS 2 terhadap simulasi. | `coppelia_ros2` tersedia untuk operasi satu-shot dan streaming terbatas; runtime Humble berjalan di Docker. |

### Setup dan pemakaian ROS 2

Host perangkat ini menjalankan Arch Linux tanpa ROS 2. Runtime Humble berjalan di Docker; image memuat dependensi `simROS2` dan paket contoh. Setup tidak mengubah paket host:

```bash
./coppelia_ros2_container.sh build
./coppelia_ros2_container.sh start
```

`coppelia_launch.sh` memilih runtime Docker otomatis setelah image tersedia. `coppelia_ros2` menjalankan operasi ROS 2 dalam container sementara dengan jaringan host, IPC host, dan `ROS_DOMAIN_ID` sama. Operasi streaming menerima `count`, `duration`, `rate`, `payloads`, `feedback_topic`, dan `feedback_type` sesuai jenis operasinya.

Verifikasi live: operasi satu-shot publish/echo topic ROS 2; service `example_interfaces/srv/AddTwoInts` menghasilkan `sum=5`; action Fibonacci mengirim feedback dan result sukses. Plugin `simROS2` berhasil dimuat. Capture/publish sequence/closed-loop telah diuji terisolasi, tetapi belum diuji live atau terhadap script scene tertentu.

### Rekomendasi urutan

1. Selesai: `coppelia_trajectory` menjalankan path hasil planner, batas joint/velocity, collision check, aksi gripper, verifikasi kontak/lift/hold/slip, serta jarak place.
2. Selesai: `coppelia_sensors` membaca data sensor terstruktur.
3. Selesai: `coppelia_mechanism` merangkum mekanisme untuk membantu pemilihan joint dan sensor.
4. Selesai: `coppelia_experiments` menjalankan episode terbatas dan membandingkan hasil.
5. Selesai: impor model dan integrasi ROS 2 opsional.

Fitur P0 melengkapi alur planner-ke-eksekusi. Keberhasilan simulasi tidak membuktikan keselamatan hardware atau sertifikasi keselamatan.

## Sumber

- [CoppeliaSim User Manual: Welcome](https://manual.coppeliarobotics.com/en/welcome.htm)
- [CoppeliaSim main features](https://manual.coppeliarobotics.com/en/coppeliaSimFeatures.htm)
- [Path/motion planning](https://manual.coppeliarobotics.com/en/pathAndMotionPlanningModules.htm)
- [Vision sensors](https://manual.coppeliarobotics.com/en/visionSensors.htm)
- [ROS 2 Interface](https://manual.coppeliarobotics.com/en/ros2Interface.htm)
- [External controller tutorial](https://manual.coppeliarobotics.com/en/externalControllerTutorial.htm)
- [Virtual commissioning of custom automation lines](https://coppeliarobotics.com/virtual-commissioning-of-custom-automation-lines)
- [Fast prototyping of mechatronic systems](https://coppeliarobotics.com/fast-prototyping-of-mechatronics-systems)
- [Official example scenes](https://github.com/CoppeliaRobotics/scenes)

## Evaluasi Workflow Lanjutan untuk Fitur MCP Mendatang

Bagian ini mengevaluasi kebutuhan workflow lanjutan yang belum terlayani oleh implementasi MCP saat ini. Analisis ini berbasis workflow teknis pada dokumentasi resmi dan studi kasus vendor, bukan klaim prevalensi atau popularitas pengguna (data survei frekuensi pengguna tidak tersedia).

### 1. Verifikasi Kontak/Grasp dan Siklus Manipulasi

- **Klaim & Kemampuan Resmi:** CoppeliaSim menyediakan kalkulasi kontak mendalam melalui `sim.getContactInfo` yang menghasilkan pasangan objek bertabrakan, titik kontak 3D, vektor gaya reaksi normal/tangensial, dan normal kontak ([sim.getContactInfo](https://manual.coppeliarobotics.com/en/regularApi/simGetContactInfo.htm)). Selain itu, skrip dapat mengintersepsi respons tabrakan dinamis melalui callback kontak `sysCall_contact` ([contactCallbackFunction](https://manual.coppeliarobotics.com/en/contactCallbackFunction.htm), [dynamicsModule](https://manual.coppeliarobotics.com/en/dynamicsModule.htm)).
- **Kondisi MCP & Kesenjangan:** `coppelia_trajectory` mengukur gaya normal, slip translasi dan sudut, lift world-Z, serta hold. `wrench_sweep` menguji gaya dan torsi ± pada tiga sumbu dengan beban/step yang ditentukan pemanggil.
- **Batas bukti:** Sweep mengukur retensi pada 12 arah beban tertentu; hasil lulus bukan sertifikat matematis force closure atau bukti di luar beban/engine yang diuji. Place tetap berbasis jarak.
- **Batas fisik:** Kontak simulasi rentan terhadap penetrasi mesh dan jitter solver. Hasil tidak membuktikan friksi material nyata, slip pada gripper elastis, reliabilitas sensor taktil, atau keselamatan hardware.

### 2. Episode Berulang, Reset Bersih, Injeksi Kegagalan, dan Validasi Keselamatan

- **Klaim & Kemampuan Resmi:** CoppeliaSim dapat mengembalikan banyak parameter objek ke kondisi saat simulasi dimulai dan menghapus objek baru saat simulasi berhenti, jika opsi scene terkait aktif ([simulationPropertiesDialog](https://manual.coppeliarobotics.com/en/simulationPropertiesDialog.htm)). `sim.resetDynamicObject` hanya membangun ulang representasi objek di physics engine; API itu bukan reset seluruh episode ([sim.resetDynamicObject](https://manual.coppeliarobotics.com/en/regularApi/simResetDynamicObject.htm)). Gangguan dinamis dapat disuntikkan melalui `sim.addForceAndTorque` ([sim.addForceAndTorque](https://manual.coppeliarobotics.com/en/regularApi/simAddForceAndTorque.htm)).
- **Kondisi MCP & Kesenjangan:** `coppelia_experiments` menerima baseline `.ttt` eksplisit, memuat ulang scene sebelum setiap episode, menerapkan joint awal saat stopped, dan mengharuskan assertions objek/proximity sensor. Reload scene tidak bergantung opsi reset saat stop. State controller eksternal, ROS 2, filesystem, dan generator acak di luar scene tidak di-reset.
- **Kebutuhan Lanjutan:** Injeksi gangguan terprogram pada eksperimen umum, penurunan torque limit, obstacle acak, dan validasi keselamatan fisik masih belum tersedia.
- **Batas & Unresolved Limits:** Simulasi tidak membuktikan kepatuhan standar keselamatan fungsional fisik (seperti ISO 10218/13849). Verifikasi hardware memerlukan perangkat nyata, E-stop, batas daya/gaya, dan prosedur penilaian risiko yang tidak disediakan runtime simulasi.

### 3. Perekaman dan Replay Dataset Sensor Sinkron

- **Klaim & Kemampuan Resmi:** Stepping mode memberi kontrol eksplisit atas batas setiap langkah simulasi; ini membantu sinkronisasi sampling, tetapi tidak menjamin determinisme universal ([simulation](https://manual.coppeliarobotics.com/en/simulation.htm)). Vision sensors menyediakan data citra dan depth, sementara force/torque dapat dibaca melalui API masing-masing ([visionSensors](https://manual.coppeliarobotics.com/en/visionSensors.htm), [sim.readForceSensor](https://manual.coppeliarobotics.com/en/sim/simReadForceSensor.htm)). CoppeliaSim juga mendukung ekspor video ([aviRecorder](https://manual.coppeliarobotics.com/en/aviRecorder.htm)).
- **Kondisi MCP & Kesenjangan:** `coppelia_sensors` hanya mengambil snapshot tunggal saat dipanggil. `coppelia_simulate` hanya mencatat posisi translasi objek dan jarak proximity sensor ke file JSON. Belum ada mekanisme streaming atau perekaman dataset multimodal terkoordinasi (RGB-D + Joint States + F/T + ground truth segmentasi) per step fisika ke format file dataset terstruktur (HDF5/MCAP/numpy) maupun fungsi pemutaran ulang (replay) pose ke dalam scene.
- **Kebutuhan Fitur Baru:** Operasi sinkronisasi capture dataset per step (`coppelia_record_dataset` atau opsi stream pada simulator) dan runner trajectory replay dari rekaman log pergerakan.
- **Batas & Unresolved Limits:** Streaming frame vision resolusi tinggi pada setiap time step menghasilkan beban I/O ZeroMQ besar dan memperlambat laju simulasi secara drastis jika ditransfer mentah ke client MCP.

### 4. Perbandingan dan Benchmarking Engine Fisika

- **Klaim & Kemampuan Resmi:** CoppeliaSim mendukung lima physics engine yang dapat diganti kapan saja: Bullet, Open Dynamics Engine (ODE), MuJoCo, Vortex Studio, dan Newton Dynamics ([dynamicsModule](https://manual.coppeliarobotics.com/en/dynamicsModule.htm)). Setiap engine memiliki karakteristik algoritma berbeda: MuJoCo mendukung massa/inersia realistis, armature joint bermotor, consecutive joint dinamik, dan benda lunak/kabel; Newton menekankan kestabilan tumpukan; sedangkan Bullet dan ODE fokus pada kecepatan bodi kaku ([physicsEngineDifferences](https://manual.coppeliarobotics.com/en/physicsEngineDifferences.htm)). Properti engine dapat dikonfigurasi melalui named property seperti `dynamicsEngine` ([propertiesReference](https://manual.coppeliarobotics.com/en/propertiesReference.htm)).
- **Kondisi MCP & Kesenjangan:** `coppelia_physics_engine` membaca/mengatur `dynamicsEngine` sebagai pasangan `[index, version]` dan `dynamicsStepSize`; perubahan hanya diizinkan saat simulasi stopped. `coppelia_physics_benchmark` menjalankan eksperimen sama pada beberapa scene `.ttt` yang disiapkan terpisah.
- **Batas tool:** Engine property memakai indeks/version CoppeliaSim, bukan nama engine. Benchmark tidak memvalidasi label atau menyamakan konfigurasi solver.
- **Batas & Unresolved Limits:** Parameter kontak antar-engine tidak memiliki korespondensi 1-ke-1 langsung (misalnya parameter friction/solimp MuJoCo vs CFM/ERP ODE); hasil simulasi antar-engine dapat berbeda signifikan pada skenario gesekan dan kontak rumit. Lisensi komersial diperlukan untuk fitur penuh Vortex Studio.

### 5. Pemantauan Jarak Jauh dan Workflow PLC / Virtual Commissioning

- **Klaim & Kemampuan Resmi:** CoppeliaSim ditujukan untuk virtual commissioning lini otomasi kustom sebelum implementasi fisik ([virtual commissioning](https://coppeliarobotics.com/virtual-commissioning-of-custom-automation-lines), [fast prototyping](https://coppeliarobotics.com/fast-prototyping-of-mechatronics-systems)). Simulator menyediakan antarmuka konektivitas seperti ZeroMQ (`simZMQ`), WebSockets (`simWS`), soket generik, serta sistem signal int/float/string untuk pertukaran data I/O dengan controller eksternal ([meansOfCommunication](https://manual.coppeliarobotics.com/en/meansOfCommunication.htm), [simWS](https://manual.coppeliarobotics.com/en/simWS.htm), [simZMQ](https://manual.coppeliarobotics.com/en/simZMQ.htm)). Integrasi PLC industri (seperti Siemens S7, Beckhoff TwinCAT, atau Rockwell) umumnya dihubungkan melalui bridge OPC UA, Modbus TCP, atau signal I/O berbasis Python/ZeroMQ.
- **Kondisi MCP & Kesenjangan:** MCP saat ini hanya mengekspos ZeroMQ untuk RPC internal server dan ROS 2 Humble via container Docker (`coppelia_ros2`). Belum ada antarmuka terstruktur untuk membaca/menulis signal I/O industri (seperti register PLC), polling status conveyor/sensor biner digital, atau bridge OPC UA / Modbus.
- **Kebutuhan Fitur Baru:** Tool manipulasi signal I/O simulasi (`coppelia_signals` get/set integer, float, string signals) atau bridge sederhana untuk pertukaran state PLC guna mendukung pengujian Software-in-the-Loop (SiL) pada virtual commissioning.
- **Batas & Unresolved Limits:** Latensi polling jaringan eksternal (OPC UA/Modbus) dapat menyebabkan desinkronisasi waktu nyata antara siklus pemindaian PLC (biasanya sub-10ms) dan langkah simulasi CoppeliaSim jika tidak dioperasikan dalam stepping mode sinkron terikat.

### Sumber Tambahan

- [CoppeliaSim: Dynamics Module](https://manual.coppeliarobotics.com/en/dynamicsModule.htm)
- [CoppeliaSim: Physics Engine Differences](https://manual.coppeliarobotics.com/en/physicsEngineDifferences.htm)
- [CoppeliaSim: Properties Reference](https://manual.coppeliarobotics.com/en/propertiesReference.htm)
- [CoppeliaSim: Contact Callback Function](https://manual.coppeliarobotics.com/en/contactCallbackFunction.htm)
- [CoppeliaSim: sim.getContactInfo](https://manual.coppeliarobotics.com/en/regularApi/simGetContactInfo.htm)
- [CoppeliaSim: sim.addForceAndTorque](https://manual.coppeliarobotics.com/en/regularApi/simAddForceAndTorque.htm)
- [CoppeliaSim: sim.resetDynamicObject](https://manual.coppeliarobotics.com/en/regularApi/simResetDynamicObject.htm)
- [CoppeliaSim: Simulation Settings Dialog](https://manual.coppeliarobotics.com/en/simulationPropertiesDialog.htm)
- [CoppeliaSim: Video Exporter](https://manual.coppeliarobotics.com/en/aviRecorder.htm)
- [CoppeliaSim: Means of Communication](https://manual.coppeliarobotics.com/en/meansOfCommunication.htm)
- [CoppeliaSim: simWS WebSocket Plugin](https://manual.coppeliarobotics.com/en/simWS.htm)
- [CoppeliaSim: simZMQ Plugin](https://manual.coppeliarobotics.com/en/simZMQ.htm)

## Prioritas Fitur Berikutnya

Prioritas di bawah adalah inferensi kebutuhan dari workflow resmi, bukan statistik popularitas pengguna. Audit hanya mencakup tool MCP dan dokumentasi yang tersedia di checkout ini.

| Prioritas | Kebutuhan pengguna | Peluang MCP | Dasar dan batas |
|---|---|---|---|
| **P0** | Ulangi eksperimen secara adil dan ukur keberhasilan tugas, bukan sekadar simulasi selesai. | Tersedia: baseline scene eksplisit, reload tiap episode, serta assertions objek/proximity sensor wajib. | Reload `.ttt` mereset scene tanpa bergantung opsi stop/reset. State sistem eksternal tidak termasuk. [Kode eksperimen](../coppeliasim_mcp/experiment_tools.py), [kontrak dan verifikasi](changes/p0-reset-contact-verification.md). |
| **P0** | Tahu apakah gripper menyentuh dan menahan benda selama dipindahkan. | Tersedia: kontak, ambang normal, batas translasi/rotasi, lift/hold, dan sweep wrench enam-sumbu yang dibatasi pengguna. | Sweep hanya menguji arah dan beban yang diminta; bukan bukti analitis force closure. Smoke sintetis bukan bukti gripper komersial atau hardware aman. [Kode trajectory](../coppeliasim_mcp/trajectory_tools.py), [bukti P0](changes/p0-reset-contact-verification.md). |
| **P1** | Mendapat dataset kamera, depth, joint, force/torque, dan state yang selaras terhadap waktu simulasi. | Tersedia melalui `coppelia_record_dataset`: rekaman bertimestamp per-step, metadata scene, sampling, batas sampel, dan ekspor JSON. Replay rekaman belum tersedia. | Sensor dibaca melalui `sensor_tools.read_one`; transfer data vision tetap berisiko membebani ZeroMQ, sehingga sampling dan batas ukuran penting. [Tool dataset](../coppeliasim_mcp/dataset_tools.py), [sensor MCP](../coppeliasim_mcp/sensor_tools.py), [vision sensors](https://manual.coppeliarobotics.com/en/visionSensors.htm). |
| **P1** | Menjalankan gerak arm yang halus dengan batas percepatan dan jerk, bukan hanya batas posisi/kecepatan. | `coppelia_trajectory` menerima batas opsional `max_acceleration` dan `max_jerk`, lalu menjalankan profil septic bertahap bersama collision check. | Batas diverifikasi dari profil diskret sesuai `steps_per_waypoint`; bukan solver Ruckig time-optimal. [Kode trajectory](../coppeliasim_mcp/trajectory_tools.py), [sim.moveToConfig](https://manual.coppeliarobotics.com/en/sim/simMoveToConfig.htm). |
| **P1** | Menguji controller ROS 2 sebagai aliran tertutup, bukan mengirim satu pesan lalu berhenti. | `coppelia_ros2` mendukung capture multi-pesan, publish sequence, dan sesi closed-loop dengan feedback topic. | Operasi dibatasi jumlah/durasi dan memakai proses CLI/container, bukan stepping sinkron dengan scene CoppeliaSim. [ROS 2 MCP](../coppeliasim_mcp/ros2_tools.py), [tutorial ROS 2](https://manual.coppeliarobotics.com/en/ros2Tutorial.htm). |
| **P2** | Membuat lingkungan navigasi dari denah, lalu menguji robot mobile di ruang yang relevan. | `coppelia_import_floorplan` mengubah pixel grayscale terklasifikasi menjadi geometri cuboid statis, dengan skala pixel, tinggi kategori, dan opsi respondable. | Ini importer MCP sendiri, bukan wrapper add-on GUI resmi. Resolusi dibatasi 1 juta pixel dan 10.000 segmen. [Kode importer](../coppeliasim_mcp/floorplan_tools.py), [import/export](https://manual.coppeliarobotics.com/en/importExport.htm). |
| **P2** | Menguji logika PLC dan I/O digital pada virtual commissioning. | `coppelia_signals` membaca/menulis integer, float, dan string signals. | Ini akses signal dalam simulasi, bukan PLC, OPC UA, atau Modbus adapter; hasil simulasi bukan safety certification. [Kode signals](../coppeliasim_mcp/signal_tools.py), [Means of communication](https://manual.coppeliarobotics.com/en/meansOfCommunication.htm). |
| **P2** | Mengetahui apakah hasil kontak dan gerak berubah saat physics engine atau solver berubah. | `coppelia_physics_engine` membaca/mengatur pasangan engine `[index, version]` dan `dynamicsStepSize`; `coppelia_physics_benchmark` menjalankan episode identik pada scene terpisah per engine. | Perubahan hanya saat stopped. Tool tidak memetakan nama engine, memvalidasi label benchmark, atau menyetarakan parameter antar-engine. [Kode physics](../coppeliasim_mcp/physics_tools.py), [kode benchmark](../coppeliasim_mcp/physics_benchmark.py), [Dynamics](https://manual.coppeliarobotics.com/en/dynamicsModule.htm), [perbedaan engine](https://manual.coppeliarobotics.com/en/physicsEngineDifferences.htm). |

Force closure tetap belum terbukti secara matematis. Tool melaporkan hasil *bounded wrench resistance* dan menyatakan `analytic_force_closure_proven=false`; keselamatan fisik memerlukan pengujian hardware dan review keselamatan terpisah.

**Status P2:** tersedia importer denah, operasi signals, inspeksi dan pengaturan physics berbasis property, serta benchmark episode lintas scene. Belum tersedia adapter PLC/network atau pemetaan engine-name otomatis.

**Catatan checkout:** impor `base64` pada `coppelia_mcp.py` diperbaiki agar snapshot dapat dilampirkan sebagai konten gambar MCP.
