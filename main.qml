import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: appWin
    width: 900
    height: 550
    visible: true
    title: "LHM"

    property var contextField: null

    function showValidationError(msg) {
        errorDialog.title = "Помилка"
        errorDialog.text = msg
        errorDialog.open()
    }

    function isValidIp(value) {
        if (value.length === 0) {
            return true
        }
        const ipv4 = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/
        if (ipv4.test(value)) {
            return true
        }
        const ipv6 = /^[0-9a-fA-F:]+$/
        return value.indexOf(":") !== -1 && ipv6.test(value)
    }

    function isValidHostname(host) {
        if (host.length === 0 || host.length > 253) {
            return false
        }
        const labels = host.split(".")
        const labelRe = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/
        for (let i = 0; i < labels.length; i += 1) {
            const label = labels[i]
            if (!labelRe.test(label)) {
                return false
            }
        }
        return true
    }

    function isValidHostList(value) {
        const trimmed = value.trim()
        if (trimmed.length === 0) {
            return true
        }
        const parts = trimmed.split(/\s+/)
        for (let i = 0; i < parts.length; i += 1) {
            if (!isValidHostname(parts[i])) {
                return false
            }
        }
        return true
    }

    function openEditMenu(field, x, y) {
        contextField = field
        editMenu.x = x
        editMenu.y = y
        editMenu.open()
    }

    Connections {
        target: appEngine
        function onErrorOccurred(msg) {
                console.error(msg)
                errorDialog.text = msg
                errorDialog.open()
            }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 6

        // Header
        Rectangle {
            Layout.fillWidth: true
            color: "#1a1a1a"
            implicitHeight: headerRow.implicitHeight + 12

            RowLayout {
                id: headerRow
                anchors.fill: parent
                anchors.margins: 6
                spacing: 10

                Label { text: "Enabled"; Layout.preferredWidth: 44 }
                Label { text: "IP"; color: "#bdbdbd"; Layout.preferredWidth: 200 }
                Label { text: "Hosts"; color: "#bdbdbd"; Layout.fillWidth: true }
            }
        }

        ListView {
            id: listView
            Layout.fillHeight: true
            Layout.fillWidth: true
            clip: true

            model: hostsModel
            currentIndex: -1

            delegate: Rectangle {
                id: delegateRoot

                property bool hovered: false

                implicitHeight: content.implicitHeight + 12
                implicitWidth: listView.width
                color: ListView.isCurrentItem ? "#2a2a2a"
                                              : (hovered ? "#202020" : "transparent")

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: "#2b2b2b"
                }

                RowLayout {
                    id: content
                    anchors.fill: parent
                    anchors.margins: 6
                    spacing: 10

                    CheckBox {
                        checked: model.enabled
                        onToggled: hostsModel.setEnabled(index, checked)
                        // Layout.preferredWidth: 44
                        Layout.alignment: Qt.AlignVCenter
                    }

                    TextField {
                        text: model.ip
                        Layout.preferredWidth: 200
                        selectByMouse: true
                        onEditingFinished: {
                            const v = text.trim()
                            if (!isValidIp(v)) {
                                showValidationError("Некоректна IP-адреса.")
                                text = model.ip
                                return
                            }
                            text = v
                            hostsModel.setIp(index, v)
                        }
                        Layout.alignment: Qt.AlignVCenter

                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.RightButton
                            onClicked: (mouse) => {
                                const pos = parent.mapToItem(appWin.contentItem, mouse.x, mouse.y)
                                openEditMenu(parent, pos.x, pos.y)
                            }
                        }
                    }

                    TextField {
                        text: model.hosts
                        Layout.fillWidth: true
                        selectByMouse: true
                        onEditingFinished: {
                            const v = text.trim()
                            if (!isValidHostList(v)) {
                                showValidationError("Некоректні імена хостів. Використовуй латиницю, цифри, дефіси та крапки.")
                                text = model.hosts
                                return
                            }
                            text = v
                            hostsModel.setHosts(index, v)
                        }
                        Layout.alignment: Qt.AlignVCenter

                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.RightButton
                            onClicked: (mouse) => {
                                const pos = parent.mapToItem(appWin.contentItem, mouse.x, mouse.y)
                                openEditMenu(parent, pos.x, pos.y)
                            }
                        }
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    propagateComposedEvents: true
                    hoverEnabled: true
                    onEntered: delegateRoot.hovered = true
                    onExited: delegateRoot.hovered = false
                    onPressed: (mouse) => {
                                   listView.currentIndex = index
                                   mouse.accepted = false
                               }
                }
            }
        }
    }

    footer: Rectangle {
        Layout.fillWidth: true
        implicitHeight: footerContent.implicitHeight + 20
        color: "#1e1e1e"

        RowLayout {
            id: footerContent
            anchors.fill: parent
            anchors.margins: 10

            Label {
                text: "● Є незастосовані зміни"
                color: "orange"
                visible: appEngine && appEngine.dirty
            }

            Item { Layout.fillWidth: true }

            Button {
                text: "Відмінити"
                enabled: appEngine && appEngine.dirty
                onClicked: appEngine && appEngine.revert()
            }

            Button {
                text: "Застосувати"
                enabled: appEngine && appEngine.dirty
                onClicked: appEngine && appEngine.apply()
            }
        }
    }

    MessageDialog {
        id: errorDialog
        title: qsTr("Error")
    }

    Menu {
        id: editMenu

        MenuItem {
            text: "Вирізати"
            enabled: appWin.contextField && !appWin.contextField.readOnly && appWin.contextField.selectedText.length > 0
            onTriggered: appWin.contextField && appWin.contextField.cut()
        }
        MenuItem {
            text: "Копіювати"
            enabled: appWin.contextField && appWin.contextField.selectedText.length > 0
            onTriggered: appWin.contextField && appWin.contextField.copy()
        }
        MenuItem {
            text: "Вставити"
            enabled: appWin.contextField && !appWin.contextField.readOnly
            onTriggered: appWin.contextField && appWin.contextField.paste()
        }
        MenuItem {
            text: "Виділити все"
            enabled: appWin.contextField
                     && !(appWin.contextField.selectionStart === 0
                          && appWin.contextField.selectionEnd === appWin.contextField.length)
            onTriggered: appWin.contextField && appWin.contextField.selectAll()
        }
    }
}
