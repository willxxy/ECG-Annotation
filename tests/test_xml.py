from ecg_annot.data_utils.prepare_xml import load_ecg_signals_only


if __name__ == "__main__":
    signals = load_ecg_signals_only("data/batch_10.xml")
    print(signals.shape)

    signals = load_ecg_signals_only("data/batch_9.xml")
    print(signals.shape)
