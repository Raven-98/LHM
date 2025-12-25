import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    width: 900
    height: 550
    visible: true
    title: "LHM"

    Connections {
        target: appEngine
        function onErrorOccurred(msg) {
                console.error(msg)
                errorDialog.errorText = msg
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
                        onEditingFinished: hostsModel.setIp(index, text)
                        Layout.alignment: Qt.AlignVCenter
                    }

                    TextField {
                        text: model.hosts
                        Layout.fillWidth: true
                        selectByMouse: true
                        onEditingFinished: hostsModel.setHosts(index, text)
                        Layout.alignment: Qt.AlignVCenter
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
        implicitHeight: footerСontent.implicitHeight + 20
        color: "#1e1e1e"

        RowLayout {
            id: footerСontent
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

    Dialog {
        id: errorDialog
        title: "Error"
        modal: true
        standardButtons: Dialog.Ok

        property string errorText: ""

        contentItem: Label {
            text: errorDialog.errorText
            wrapMode: Text.WordWrap
            width: Math.min(700, parent ? parent.width : 700)
        }
    }
}
