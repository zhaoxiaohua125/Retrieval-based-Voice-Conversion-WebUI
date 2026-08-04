from app import AppScheduler, ConfigStore, BusMessage, ModuleId, SignalType, setup_app_logging

setup_app_logging()
bus = AppScheduler.instance().start()
store = ConfigStore().load()
store.set('rvc.f0_up_key', 0).save()
bus.publish(BusMessage(SignalType.STATUS, ModuleId.UI, {'state': 'ready'}))
bus.shutdown()