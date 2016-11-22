#!/usr/bin/env hy

(import [contextlib]
        [functools]
        [glob]
        [os.path]
        [random]
        [time]
        [collections [namedtuple]]
        [PIL [Image]]
        [rx [Observable]]
        [rx.subjects [Subject]]
        [rx.concurrency [EventLoopScheduler ThreadPoolScheduler]]
        [config]
        [camera [context :as camera_context]]
        [display [show_image load_image play_sound]]
        [display [context :as display_context]]
        [gpio [PushButton setup_out switch_on switch_off flash]]
        [gpio [context :as gpio_context]]
        [util [const]])


(defn blink_once [led conf]
  (switch_on led)
  (time.sleep (/ conf.blink.interval 2))
  (switch_off led))


(defn lightshow [seconds conf]
  (switch_off conf.led.green)
  (switch_off conf.led.yellow)
  (switch_off conf.led.red)
  (time.sleep seconds)
  (switch_on conf.led.green)
  (time.sleep seconds)
  (switch_on conf.led.yellow)
  (time.sleep seconds)
  (switch_on conf.led.red)
  (switch_off conf.led.green)
  (switch_off conf.led.yellow)
  (switch_off conf.led.red))


(defn show_montage [file_name conf]
  (-> file_name
      (load_image)
      (Image.Image.resize conf.screen.size Image.ANTIALIAS)
      (show_image conf.display conf.screen.offset)))


(defn show_overlay [file_name position seconds conf]
  (setv img (->> file_name (os.path.join conf.resource_path) Image.open)
        width (-> img.size (get 0) (+ 31) (// 32) (* 32))
        height (-> img.size (get 1) (+ 15) (// 16) (* 16))
        pad (Image.new "RGB" (, width height)))
  (pad.paste img position)
  (with [(conf.camera.overlay (pad.tostring) :size img.size :alpha 64 :layer 3)]
    (time.sleep seconds)))


(defn count_down [number conf]
  (show_overlay
    (conf.photo.countdown.prepare.image_mask.format number)
    conf.photo.countdown.prepare.image_position
    2
    conf)
  (for [i [3 2 1]]
    (-> i (conf.photo.countdown.count.sound_mask.format) (play_sound))
    (show_overlay
      (conf.photo.countdown.count.image_mask.format i)
      conf.photo.countdown.count.image_position
      1
      conf))
  (show_overlay
    conf.photo.countdown.smile.image_file
    conf.photo.countdown.smile.image_position
    1.5
    conf)
  (if conf.photo.countdown.songs.enabled
      (-> conf.photo.countdown.songs.glob_mask
          (glob.glob)
          (random.choice)
          (play_sound))))


(defn detect_push [prev curr]
  (assert (<= prev.time curr.time))
  (if (and (is_pressed prev) (is_released curr))
      (ButtonPushed prev.command prev.log prev.time curr.time)
      curr))


(defn non_overlapping [prev curr]
  (assert (<= prev.pressed curr.pressed))
  (if (<= prev.released curr.pressed)
      curr
      prev))


(defn to_command [pushed]
  (if (>= pushed.command.hold (- pushed.released pushed.pressed))
      pushed.command
      pushed.log))


(defn paste-to [image photo i layout]
  (image.paste
    (photo.resize layout.size Image.ANTIALIAS)
    (get layout.box i)))


(setv Log (namedtuple "Log" "info")
      Shoot (namedtuple "Shoot" "hold code")
      Quit (namedtuple "Quit" "hold code")
      ShowRandomMontage (namedtuple "ShowRandomMontage" "")
      Blink (namedtuple "Blink" "")
      ButtonPressed (namedtuple "ButtonPressed" "time command")
      ButtonReleased (namedtuple "ButtonReleased" "time")
      ButtonPushed (namedtuple "ButtonPushed" "command log pressed released")
      is_pressed (functools.partial instance? ButtonPressed)
      is_released (functools.partial instance? ButtonReleased)
      is_pushed (functools.partial instance? ButtonPushed))


(with-decorator functools.singledispatch
  (defn handle_command [cmd conf]
    (raise NotImplementedError)))


(with-decorator (handle_command.register Log)
  (defn handle_log [cmd conf]
    (print cmd.info)))


(with-decorator (handle_command.register Shoot)
  (defn handle_shoot [cmd conf]
    (with [conf.shooting_lock]
      (with [(flash conf.photo.lights)]
        (with [(conf.camera.preview)]
          (setv timestamp (time.strftime conf.photo.time_mask)
                file_names (-> timestamp
                               (conf.photo.file_mask.format)
                               (conf.camera.shoot))
                montage (conf.montage.image.copy)
                printout (conf.printout.image.copy))
          (for [i conf.photo.range]
            (count_down (inc i) conf)
            (setv photo (Image.open (next file_names)))
            (paste-to montage (photo.convert "RGBA") i conf.montage.layout)
            (paste-to printout photo i conf.printout.layout)
            (time.sleep 5))
          (setv file_name (conf.montage.file_mask.format timestamp))
          (-> Image
              (.blend montage conf.montage.watermark.image 0.25)
              (.save file_name))
          (show_montage file_name conf)))
      (-> timestamp (conf.printout.file_mask.format) (printout.save))
      (time.sleep conf.montage.interval))))


(with-decorator (handle_command.register Quit)
  (defn handle_quit [cmd conf]
    (conf.exit_code.put cmd.code)))


(with-decorator (handle_command.register ShowRandomMontage)
  (defn handle_show_montage [cmd conf]
    (if (conf.shooting_lock.acquire :blocking False)
        (try
          (-> conf.montage.glob_mask
              (glob.glob)
              (random.choice)
              (show_montage conf))
          (finally
            (conf.shooting_lock.release))))))


(with-decorator (handle_command.register Blink)
  (defn handle_blink [cmd conf]
    (if (conf.shooting_lock.acquire :blocking False)
        (do
          (conf.shooting_lock.release)
          (blink_once conf.led.yellow conf))
        (blink_once conf.led.red conf))))


(defclass Button [object]
  (defn --init-- [self command event bounce-time scheduler]
    (PushButton.--init-- self event.port bounce-time)
    (setv self.command (command :hold event.hold :code event.code)
          self.log (Log :info event.info)
          self.events (Subject)
          self.pushes (-> self.events
                          (.observe_on scheduler)
                          (.scan detect_push)
                          (.where is_pushed)
                          (.distinct_until_changed))))
  (defn pressed [self]
    (-> (time.time) (ButtonPressed self) (self.events.on_next)))
  (defn released [self]
    (-> (time.time) (ButtonReleased) (self.events.on_next))))


(with-decorator contextlib.contextmanager
  (defn bus_context [conf]
    (setv event_loop (EventLoopScheduler)
          buttons [
            (-> (Button Shoot conf.event.shoot conf.bounce_time event_loop))
            (-> (Button Quit conf.event.quit conf.bounce_time event_loop))
            (-> (Button Quit conf.event.reboot conf.bounce_time event_loop))
            (-> (Button Quit conf.event.shutdown conf.bounce_time event_loop))]
          bus (Subject)
          blinker_ticks (Observable.interval conf.blink.interval)
          montage_ticks (Observable.interval conf.montage.interval)
          handler (-> Observable
                      (.merge (list-comp button.pushes [button buttons]))
                      (.scan non_overlapping :seed (ButtonPushed None None 0 0))
                      (.distinct_until_changed)
                      (.map to_command)
                      (.merge
                          (ThreadPoolScheduler :max_workers conf.workers)
                          bus
                          (-> (Blink) const blinker_ticks.map)
                          (-> (ShowRandomMontage) const montage_ticks.map))
                      (.subscribe :on_next (fn [c] (handle_command c conf)))))
    (try
      (yield bus)
      (finally
        (handler.dispose)
        (montage_ticks.dispose)
        (blinker_ticks.dispose)
        (bus.dispose)
        (for [button buttons]
          (button.events.dispose))))))


(defn run [conf]
  (with [(gpio_context)]
    (for [light conf.photo.lights]
      (setup_out light))
    (setup_out conf.led.red)
    (setup_out conf.led.yellow)
    (setup_out conf.led.green)
    (switch_on conf.led.green)
    (with [conf.display (display_context :size conf.screen.size)
           conf.camera (camera_context :size conf.photo.size)
           conf.bus (bus_context conf)]
      (try
        (conf.exit_code.get)
        (finally
          (lightshow 1 conf))))))


(defmain [&rest args]
  (import argparse
          [.config [config]])
  (setv parser (argparse.ArgumentParser :description "FotoBox Programm."))
  (parser.add_argument
      "--config"
      :default "fotobox.json"
      :type str
      :help "path to config file")
  (-> (parser.parse_args) (. config) (config) (run)))
